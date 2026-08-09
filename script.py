import os
import re
import html
import requests
import time
from datetime import datetime


# =========================================================
# الإعدادات الأساسية
# =========================================================

FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_TOKEN")

IG_USER_ID = os.getenv("IG_USER_ID")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")

DB_FILE = "last_news_id.txt"
IG_DB_FILE = "last_instagram_id.txt"
RESET_FILE = ".news_history_reset"

SOURCE_CHANNEL = "Castlenewsiq"

# الحد الأقصى 5 منشورات في كل تشغيل
MAX_POSTS_PER_RUN = 5

# 10 ثوانٍ بين المنشورات
POST_DELAY_SECONDS = 10

# تصفير السجل كل 48 ساعة
HISTORY_RESET_SECONDS = 48 * 60 * 60

TEMP_MEDIA_DIR = "tmp_media"


# =========================================================
# وقت التشغيل
# =========================================================

def is_work_time():
    """
    التشغيل اليدوي من GitHub Actions يعمل دائمًا
    حتى لو كان خارج ساعات العمل.

    التشغيل المجدول يبقى ضمن ساعات العمل الطبيعية.
    """

    # تشغيل يدوي من GitHub Actions
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        print("🖐️ تشغيل يدوي: تجاوز ساعات العمل.")
        return True

    # دعم FORCE_RUN أيضًا إذا تم استخدامه مستقبلًا
    if os.getenv("FORCE_RUN") == "1":
        print("🖐️ FORCE_RUN مفعّل: تجاوز ساعات العمل.")
        return True

    current_hour = (datetime.utcnow().hour + 3) % 24

    return 9 <= current_hour <= 23


# =========================================================
# تصفير سجل الأخبار
# =========================================================

def reset_history_if_needed():
    """
    تصفير سجل Facebook وInstagram كل 48 ساعة.
    """

    now = time.time()

    try:
        with open(RESET_FILE, "r", encoding="utf-8") as f:
            last_reset = float(f.read().strip())

    except (FileNotFoundError, ValueError):
        last_reset = 0

    if now - last_reset >= HISTORY_RESET_SECONDS:

        with open(DB_FILE, "w", encoding="utf-8") as f:
            f.write("")

        with open(IG_DB_FILE, "w", encoding="utf-8") as f:
            f.write("")

        with open(RESET_FILE, "w", encoding="utf-8") as f:
            f.write(str(now))

        print("🧹 تم تصفير سجل الأخبار.")


# =========================================================
# تنظيف النص
# =========================================================

def clean_news_text(text):
    """
    تنظيف Caption وحذف روابط Telegram وتوقيع القناة.
    """

    if not text:
        return ""

    text = html.unescape(text)

    # تحويل BR إلى أسطر
    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    # حذف روابط Telegram
    text = re.sub(
        r"https?://(?:www\.)?t\.me/[A-Za-z0-9_+\-/?.=&%#]+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # حذف اسم القناة
    text = re.sub(
        r"(?<!\w)@Castlenewsiq\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # حذف توقيع القناة
    text = re.sub(
        r"للمزيد\s*من\s*الأخبار\s*اشترك\s*في\s*قناتنا\s*:?\s*👇?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"اشترك\s*في\s*قناتنا\s*:?\s*👇?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # إزالة HTML
    text = re.sub(
        r"<[^>]+>",
        "",
        text,
    )

    # تنظيف الفراغات
    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.splitlines()
    ]

    text = "\n".join(
        line for line in lines if line
    )

    return text.strip()


# =========================================================
# Facebook History
# =========================================================

def load_history():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return {
                line.strip()
                for line in f
                if line.strip()
            }

    except FileNotFoundError:
        return set()


def save_history(msg_id):
    with open(DB_FILE, "a", encoding="utf-8") as f:
        f.write(f"{msg_id}\n")


# =========================================================
# Instagram History
# =========================================================

def load_instagram_history():
    try:
        with open(IG_DB_FILE, "r", encoding="utf-8") as f:
            return {
                line.strip()
                for line in f
                if line.strip()
            }

    except FileNotFoundError:
        return set()


def save_instagram_history(msg_id):
    with open(IG_DB_FILE, "a", encoding="utf-8") as f:
        f.write(f"{msg_id}\n")


# =========================================================
# جلب منشورات Telegram
# =========================================================

def fetch_latest_posts(limit=MAX_POSTS_PER_RUN):
    """
    جلب آخر منشورات القناة العامة.
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        )
    }

    print(
        f"🌐 الاتصال بقناة: {SOURCE_CHANNEL}"
    )

    res = requests.get(
        f"https://t.me/s/{SOURCE_CHANNEL}",
        headers=headers,
        timeout=20,
    )

    print(
        f"🔍 حالة الاستجابة: {res.status_code}"
    )

    res.raise_for_status()

    items = re.findall(
        r'data-post="[^"/]+/(\d+)"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        res.text,
        re.DOTALL,
    )

    print(
        f"📊 عدد المنشورات المكتشفة: {len(items)}"
    )

    return items[-limit:]


# =========================================================
# تحليل المنشور
# =========================================================

def parse_post(msg_id, item):
    """
    فقط:
    - صورة منفردة
    - فيديو منفرد

    يتم تجاهل:
    - النصوص فقط
    - Albums
    - الأنواع غير المدعومة
    """

    # Album / grouped media
    if re.search(
        r"tgme_widget_message_grouped|data-album=",
        item,
        flags=re.IGNORECASE,
    ):
        return None

    # Caption
    msg_match = re.search(
        r'class="tgme_widget_message_text[^>]*>(.*?)</div>',
        item,
        re.DOTALL | re.IGNORECASE,
    )

    raw_text = (
        msg_match.group(1)
        if msg_match
        else ""
    )

    caption = clean_news_text(raw_text)

    # =====================================================
    # صورة منفردة
    # =====================================================

    photo_match = re.search(
        r'tgme_widget_message_photo_wrap[^>]*style="[^"]*background-image:url\([\'"]?([^\'")]+)',
        item,
        re.IGNORECASE,
    )

    if photo_match:

        return {
            "id": str(msg_id),
            "type": "photo",
            "url": html.unescape(
                photo_match.group(1)
            ),
            "caption": caption,
        }

    # fallback للصورة
    if re.search(
        r"tgme_widget_message_photo_wrap",
        item,
        re.IGNORECASE,
    ):

        img_match = re.search(
            r'<img[^>]+src="([^"]+)"',
            item,
            re.IGNORECASE,
        )

        if img_match:

            return {
                "id": str(msg_id),
                "type": "photo",
                "url": html.unescape(
                    img_match.group(1)
                ),
                "caption": caption,
            }

    # =====================================================
    # فيديو منفرد
    # =====================================================

    video_match = re.search(
        r'<video[^>]+(?:src|data-src)="([^"]+)"',
        item,
        re.IGNORECASE,
    )

    if not video_match:

        video_match = re.search(
            r'<source[^>]+src="([^"]+)"',
            item,
            re.IGNORECASE,
        )

    if not video_match:

        video_match = re.search(
            r'tgme_widget_message_video[^>]+[^>]*data-video="([^"]+)"',
            item,
            re.IGNORECASE,
        )

    if video_match:

        return {
            "id": str(msg_id),
            "type": "video",
            "url": html.unescape(
                video_match.group(1)
            ),
            "caption": caption,
        }

    # النصوص فقط أو الأنواع الأخرى
    return None


# =========================================================
# تنزيل الوسائط
# =========================================================

def download_media(media_url, media_type, msg_id):
    """
    تنزيل الوسيط مؤقتًا داخل GitHub Runner فقط.
    """

    os.makedirs(
        TEMP_MEDIA_DIR,
        exist_ok=True,
    )

    ext = (
        ".mp4"
        if media_type == "video"
        else ".jpg"
    )

    path = os.path.join(
        TEMP_MEDIA_DIR,
        f"{msg_id}{ext}",
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        )
    }

    try:

        with requests.get(
            media_url,
            headers=headers,
            stream=True,
            timeout=120,
        ) as r:

            r.raise_for_status()

            with open(path, "wb") as f:

                for chunk in r.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:
                        f.write(chunk)

        return path

    except Exception:

        remove_temp_file(path)

        raise


# =========================================================
# Facebook
# =========================================================

def post_to_facebook(
    media_path,
    media_type,
    message="",
):
    """
    مسار Facebook مستقل.
    """

    try:

        if media_type == "photo":

            url = (
                f"https://graph.facebook.com/v19.0/"
                f"{FB_PAGE_ID}/photos"
            )

            payload = {
                "caption": message,
                "access_token": FB_PAGE_TOKEN,
            }

            with open(
                media_path,
                "rb",
            ) as media_file:

                r = requests.post(
                    url,
                    data=payload,
                    files={
                        "source": media_file
                    },
                    timeout=120,
                )

        else:

            url = (
                f"https://graph.facebook.com/v19.0/"
                f"{FB_PAGE_ID}/videos"
            )

            payload = {
                "description": message,
                "access_token": FB_PAGE_TOKEN,
            }

            with open(
                media_path,
                "rb",
            ) as media_file:

                r = requests.post(
                    url,
                    data=payload,
                    files={
                        "source": media_file
                    },
                    timeout=300,
                )

        if r.status_code == 200:

            print(
                f"✅ Facebook: تم نشر "
                f"{media_type} بنجاح"
            )

            return True

        print(
            f"❌ Facebook Error: "
            f"{r.status_code} - "
            f"{r.text[:500]}"
        )

        return False

    except Exception as e:

        print(
            f"⚠️ FB Connection Error: {e}"
        )

        return False


# =========================================================
# Instagram - Instagram Login
# =========================================================

def instagram_request(
    method,
    endpoint,
    **kwargs,
):
    """
    طلب مستقل إلى Instagram API.

    يستخدم:
    graph.instagram.com

    وInstagram User Access Token.
    """

    if not IG_ACCESS_TOKEN:

        print(
            "⚠️ Instagram: "
            "IG_ACCESS_TOKEN غير موجود."
        )

        return None

    url = (
        f"https://graph.instagram.com/v23.0/"
        f"{endpoint.lstrip('/')}"
    )

    headers = kwargs.pop(
        "headers",
        {},
    )

    headers["Authorization"] = (
        f"Bearer {IG_ACCESS_TOKEN}"
    )

    try:

        return requests.request(
            method,
            url,
            headers=headers,
            timeout=120,
            **kwargs,
        )

    except Exception as e:

        print(
            f"⚠️ Instagram Connection Error: {e}"
        )

        return None


# =========================================================
# اختبار Token واستخراج Instagram User ID
# =========================================================

def test_instagram_token():
    """
    التحقق من أن Instagram Access Token يعمل
    واستخراج الحساب المرتبط به تلقائيًا.

    إذا كان IG_USER_ID الموجود في GitHub خاطئًا،
    سيتم استخدام ID الذي تعيده Meta لهذا الـ Token.
    """

    global IG_USER_ID

    if not IG_ACCESS_TOKEN:

        print(
            "❌ Instagram: "
            "IG_ACCESS_TOKEN غير موجود."
        )

        return False

    print(
        "🔎 Instagram: فحص Access Token..."
    )

    r = instagram_request(
        "GET",
        "me",
        params={
            "fields": "id,username"
        },
    )

    if r is None:
        return False

    print(
        f"🔎 Instagram Token Status: "
        f"{r.status_code}"
    )

    if r.status_code != 200:

        print(
            "❌ Instagram Token Error: "
            f"{r.text[:1000]}"
        )

        return False

    try:

        data = r.json()

    except Exception:

        print(
            "❌ Instagram: "
            "تعذر قراءة استجابة Meta."
        )

        return False

    detected_id = data.get("id")
    username = data.get("username")

    if not detected_id:

        print(
            "❌ Instagram: "
            "Meta لم ترجع User ID."
        )

        print(
            f"📋 Response: {data}"
        )

        return False

    # استخدام ID الحقيقي المرتبط بالـ Token
    IG_USER_ID = str(detected_id)

    print(
        "✅ Instagram Token صالح."
    )

    print(
        f"👤 Instagram Username: "
        f"{username or 'غير متوفر'}"
    )

    print(
        f"🆔 Instagram User ID: "
        f"{IG_USER_ID}"
    )

    return True


# =========================================================
# Instagram - نشر
# =========================================================

def post_to_instagram(
    media_url,
    media_type,
    caption="",
):
    """
    نشر صورة أو فيديو على Instagram.

    لا يعتمد على Facebook.
    """

    if not IG_USER_ID:

        print(
            "⚠️ Instagram: "
            "IG_USER_ID غير موجود."
        )

        return False

    if not IG_ACCESS_TOKEN:

        print(
            "⚠️ Instagram: "
            "IG_ACCESS_TOKEN غير موجود."
        )

        return False

    caption = (
        caption or ""
    )[:2200]

    # =====================================================
    # إنشاء Container
    # =====================================================

    if media_type == "photo":

        payload = {
            "image_url": media_url,
            "caption": caption,
        }

    elif media_type == "video":

        payload = {
            "media_type": "REELS",
            "video_url": media_url,
            "caption": caption,
        }

    else:

        return False

    print(
        f"📡 Instagram: إنشاء Container "
        f"للـ {media_type}..."
    )

    r = instagram_request(
        "POST",
        f"{IG_USER_ID}/media",
        data=payload,
    )

    if r is None:
        return False

    if r.status_code != 200:

        print(
            f"❌ Instagram Container Error: "
            f"{r.status_code} - "
            f"{r.text[:1000]}"
        )

        return False

    try:

        creation_id = (
            r.json().get("id")
        )

    except Exception:

        creation_id = None

    if not creation_id:

        print(
            "❌ Instagram: "
            "لم يتم استلام creation_id."
        )

        return False

    print(
        f"🆔 Instagram Container: "
        f"{creation_id}"
    )

    # =====================================================
    # انتظار المعالجة
    # =====================================================

    max_checks = (
        60
        if media_type == "video"
        else 20
    )

    for attempt in range(
        max_checks
    ):

        time.sleep(5)

        status = instagram_request(
            "GET",
            creation_id,
            params={
                "fields":
                    "status_code,status"
            },
        )

        if status is None:
            continue

        if status.status_code != 200:

            print(
                f"⚠️ Instagram Status Error: "
                f"{status.status_code} - "
                f"{status.text[:500]}"
            )

            continue

        try:

            data = status.json()

        except Exception:

            data = {}

        status_code = str(
            data.get(
                "status_code",
                "",
            )
        ).upper()

        if status_code == "FINISHED":

            print(
                "✅ Instagram: "
                "تم تجهيز الـ Container."
            )

            break

        if status_code in {
            "ERROR",
            "EXPIRED",
        }:

            print(
                "❌ Instagram: "
                "فشل تجهيز الوسائط."
            )

            print(
                f"📋 التفاصيل: {data}"
            )

            return False

        print(
            f"⏳ Instagram: انتظار معالجة "
            f"{media_type} "
            f"({attempt + 1}/{max_checks}) - "
            f"{status_code or 'PROCESSING'}"
        )

    else:

        print(
            "❌ Instagram: "
            "انتهت مهلة انتظار معالجة الوسائط."
        )

        return False

    # =====================================================
    # نشر Container
    # =====================================================

    print(
        "📤 Instagram: نشر الـ Container..."
    )

    publish = instagram_request(
        "POST",
        f"{IG_USER_ID}/media_publish",
        data={
            "creation_id": creation_id
        },
    )

    if publish is None:
        return False

    if publish.status_code == 200:

        print(
            f"✅ Instagram: تم نشر "
            f"{media_type} بنجاح"
        )

        return True

    print(
        f"❌ Instagram Publish Error: "
        f"{publish.status_code} - "
        f"{publish.text[:1000]}"
    )

    return False


# =========================================================
# حذف الملفات المؤقتة
# =========================================================

def remove_temp_file(path):
    """
    حذف الملف سواء نجح النشر أو فشل.
    """

    if not path:
        return

    try:

        if os.path.exists(path):

            os.remove(path)

            print(
                f"🗑️ تم حذف الملف المؤقت: "
                f"{path}"
            )

    except OSError as e:

        print(
            f"⚠️ تعذر حذف الملف المؤقت "
            f"{path}: {e}"
        )


def cleanup_temp_dir():

    try:

        if not os.path.isdir(
            TEMP_MEDIA_DIR
        ):
            return

        for name in os.listdir(
            TEMP_MEDIA_DIR
        ):

            remove_temp_file(
                os.path.join(
                    TEMP_MEDIA_DIR,
                    name,
                )
            )

        try:

            os.rmdir(
                TEMP_MEDIA_DIR
            )

        except OSError:

            pass

    except OSError as e:

        print(
            f"⚠️ خطأ بتنظيف "
            f"مجلد الوسائط: {e}"
        )


# =========================================================
# Main
# =========================================================

def main():

    print(
        "🚀 بدء تنفيذ البوت..."
    )

    # التشغيل اليدوي يتجاوز الوقت
    if not is_work_time():

        print(
            "🌙 خارج وقت العمل."
        )

        return

    # =====================================================
    # Instagram Token Check
    # =====================================================

    instagram_ready = test_instagram_token()

    if not instagram_ready:

        print(
            "⚠️ Instagram: "
            "فشل فحص Token."
        )

        print(
            "⚠️ سيتم الاستمرار في Facebook "
            "بشكل طبيعي."
        )

    # =====================================================
    # History
    # =====================================================

    reset_history_if_needed()

    cleanup_temp_dir()

    fb_history = load_history()

    ig_history = load_instagram_history()

    try:

        items = fetch_latest_posts(
            MAX_POSTS_PER_RUN
        )

        if not items:

            print(
                "⚠️ تنبيه: "
                "لم يتم العثور على أي منشورات."
            )

            return

        # الأقدم أولًا ضمن آخر 5
        for msg_id, item in items:

            sig = msg_id.strip()

            # إذا نجح على المنصتين سابقًا
            if (
                sig in fb_history
                and sig in ig_history
            ):
                continue

            print(
                f"📌 فحص المنشور رقم: "
                f"{sig}"
            )

            post = parse_post(
                sig,
                item,
            )

            # =================================================
            # تجاهل النصوص وAlbums
            # =================================================

            if not post:

                print(
                    f"⏭️ تجاهل المنشور "
                    f"{sig}: نص فقط أو "
                    f"Album/نوع غير مدعوم."
                )

                # تسجيل المنشور المتجاهل
                if sig not in fb_history:

                    save_history(sig)

                    fb_history.add(sig)

                if sig not in ig_history:

                    save_instagram_history(sig)

                    ig_history.add(sig)

                continue

            temp_path = None

            try:

                # =============================================
                # Facebook
                # =============================================

                if sig not in fb_history:

                    print(
                        f"📘 Facebook: معالجة "
                        f"{post['type']}..."
                    )

                    temp_path = download_media(
                        post["url"],
                        post["type"],
                        sig,
                    )

                    fb_success = post_to_facebook(
                        temp_path,
                        post["type"],
                        post["caption"],
                    )

                    if fb_success:

                        save_history(sig)

                        fb_history.add(sig)

                        print(
                            "💾 Facebook: "
                            "تم حفظ المعرف بنجاح."
                        )

                    else:

                        print(
                            "⚠️ Facebook: "
                            "فشل النشر، "
                            "لكن سيستمر Instagram."
                        )

                    # حذف ملف Facebook
                    remove_temp_file(
                        temp_path
                    )

                    temp_path = None

                # =============================================
                # Instagram
                # =============================================

                if (
                    instagram_ready
                    and sig not in ig_history
                ):

                    print(
                        f"📸 Instagram: معالجة "
                        f"{post['type']}..."
                    )

                    ig_success = post_to_instagram(
                        post["url"],
                        post["type"],
                        post["caption"],
                    )

                    if ig_success:

                        save_instagram_history(
                            sig
                        )

                        ig_history.add(sig)

                        print(
                            "💾 Instagram: "
                            "تم حفظ المعرف بنجاح."
                        )

                    else:

                        print(
                            "⚠️ Instagram: "
                            "فشل النشر، "
                            "ولا يؤثر ذلك على Facebook."
                        )

                elif not instagram_ready:

                    print(
                        "⏭️ Instagram: "
                        "تم تخطيه بسبب فشل المصادقة."
                    )

            except Exception as e:

                print(
                    f"⚠️ خطأ في المنشور "
                    f"{sig}: {e}"
                )

            finally:

                # حذف أي ملف متبقٍ
                remove_temp_file(
                    temp_path
                )

            # 10 ثوانٍ بين المنشورات
            time.sleep(
                POST_DELAY_SECONDS
            )

    except Exception as e:

        print(
            f"⚠️ خطأ عام: {e}"
        )

    finally:

        cleanup_temp_dir()


# =========================================================
# تشغيل البرنامج
# =========================================================

if __name__ == "__main__":
    main()
