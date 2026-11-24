import os
import re
import html
import requests
import time
from datetime import datetime
from nacl import encoding, public

# =========================================================
# الإعدادات الأساسية
# =========================================================

FB_PAGE_ID = os.getenv("FB_PAGE_ID")
FB_PAGE_TOKEN = os.getenv("FB_TOKEN")

IG_USER_ID = os.getenv("IG_USER_ID")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")

# Threads
THREADS_USER_ID = os.getenv("THREADS_USER_ID")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

# GitHub Secrets Auto-Refresh
GH_PAT = os.getenv("GH_PAT")
GITHUB_REPOSITORY = os.getenv(
    "GITHUB_REPOSITORY",
    "hiloo00964-spec/Castlenewsiq",
)

DB_FILE = "last_news_id.txt"
IG_DB_FILE = "last_instagram_id.txt"
THREADS_DB_FILE = "last_threads_id.txt"
RESET_FILE = ".news_history_reset"

IG_REFRESH_FILE = ".ig_token_refresh"
THREADS_REFRESH_FILE = ".threads_token_refresh"

# تجديد التوكن كل 45 يوماً
TOKEN_REFRESH_INTERVAL_SECONDS = 45 * 24 * 60 * 60

SOURCE_CHANNEL = "Castlenewsiq"

# الحد الأقصى 10 منشورات في كل تشغيل
MAX_POSTS_PER_RUN = 10

# الحد الأقصى لعناصر الـAlbum في منشور واحد
MAX_ALBUM_ITEMS = 20

# 10 ثوانٍ بين المنشورات
POST_DELAY_SECONDS = 10

# تصفير السجل كل 7 أيام
HISTORY_RESET_SECONDS = 7 * 24 * 60 * 60

TEMP_MEDIA_DIR = "tmp_media"

# Threads API
THREADS_API_BASE = "https://graph.threads.net"


# =========================================================
# وقت التشغيل
# =========================================================

def is_work_time():
    """
    التشغيل اليدوي من GitHub Actions يعمل دائمًا.
    التشغيل المجدول يبقى ضمن ساعات العمل الطبيعية.
    """
    if os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        print("🖐️ تشغيل يدوي: تجاوز ساعات العمل.")
        return True

    if os.getenv("FORCE_RUN") == "1":
        print("🖐️ FORCE_RUN مفعّل: تجاوز ساعات العمل.")
        return True

    current_hour = (datetime.utcnow().hour + 3) % 24
    # ساعات العمل بتوقيت العراق: 09:00 - 23:00 + 00:00
    return (9 <= current_hour <= 23) or current_hour == 0


# =========================================================
# تحديث أسرار GitHub Secrets وتجديد التوكنات تلقائياً
# =========================================================

def update_github_secret(secret_name, secret_value):
    """
    تشفير التوكن الجديد باستخدام PyNaCl وحفظه في GitHub Secrets.
    """
    if not GH_PAT:
        print(
            f"⚠️ GitHub Secrets: GH_PAT غير موجود، "
            f"تعذر تحديث {secret_name}."
        )
        return False

    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        key_url = (
            f"https://api.github.com/repos/"
            f"{GITHUB_REPOSITORY}/actions/secrets/public-key"
        )
        key_res = requests.get(
            key_url,
            headers=headers,
            timeout=30,
        )

        if key_res.status_code != 200:
            print(
                f"❌ GitHub Public Key Error: "
                f"{key_res.status_code} - {key_res.text[:500]}"
            )
            return False

        key_data = key_res.json()
        key_id = key_data.get("key_id")
        public_key_b64 = key_data.get("key")

        if not key_id or not public_key_b64:
            print(
                "❌ GitHub Public Key: بيانات المفتاح ناقصة."
            )
            return False

        public_key = public.PublicKey(
            public_key_b64.encode("utf-8"),
            encoding.Base64Encoder(),
        )
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(
            secret_value.encode("utf-8")
        )
        encrypted_value = (
            encoding.Base64Encoder()
            .encode(encrypted)
            .decode("utf-8")
        )

        secret_url = (
            f"https://api.github.com/repos/"
            f"{GITHUB_REPOSITORY}/actions/secrets/{secret_name}"
        )
        put_res = requests.put(
            secret_url,
            headers=headers,
            json={
                "encrypted_value": encrypted_value,
                "key_id": key_id,
            },
            timeout=30,
        )

        if put_res.status_code in (201, 204):
            print(
                f"🔐 GitHub Secret: تم تحديث "
                f"{secret_name} بنجاح."
            )
            return True

        print(
            f"❌ GitHub Secret Update Error ({secret_name}): "
            f"{put_res.status_code} - {put_res.text[:500]}"
        )
        return False

    except Exception as e:
        print(
            f"⚠️ GitHub Secret Connection Error ({secret_name}): {e}"
        )
        return False


def refresh_instagram_token_if_needed():
    """
    تجديد IG_ACCESS_TOKEN تلقائياً كل 45 يوماً وحفظه في GitHub Secrets.
    """
    global IG_ACCESS_TOKEN

    if not IG_ACCESS_TOKEN:
        return

    now = time.time()

    try:
        with open(IG_REFRESH_FILE, "r", encoding="utf-8") as f:
            last_refresh = float(f.read().strip())
    except (FileNotFoundError, ValueError):
        last_refresh = 0

    if now - last_refresh < TOKEN_REFRESH_INTERVAL_SECONDS:
        return

    print(
        "🔄 Instagram: محاولة تجديد Access Token التلقائي..."
    )

    try:
        r = requests.get(
            "https://graph.instagram.com/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": IG_ACCESS_TOKEN,
            },
            timeout=30,
        )

        if r.status_code != 200:
            print(
                f"⚠️ Instagram Refresh Error: "
                f"{r.status_code} - {r.text[:500]}"
            )
            return

        data = r.json()
        new_token = data.get("access_token")

        if not new_token:
            print(
                "⚠️ Instagram Refresh: لم يتم استلام توكن جديد."
            )
            return

        if update_github_secret("IG_ACCESS_TOKEN", new_token):
            IG_ACCESS_TOKEN = new_token
            with open(IG_REFRESH_FILE, "w", encoding="utf-8") as f:
                f.write(str(now))
            print(
                "✅ Instagram: تم تجديد التوكن وتحديث "
                ".ig_token_refresh بنجاح."
            )

    except Exception as e:
        print(
            f"⚠️ Instagram Refresh Connection Error: {e}"
        )


def refresh_threads_token_if_needed():
    """
    تجديد THREADS_ACCESS_TOKEN تلقائياً كل 45 يوماً وحفظه في GitHub Secrets.
    """
    global THREADS_ACCESS_TOKEN

    if not THREADS_ACCESS_TOKEN:
        return

    now = time.time()

    try:
        with open(THREADS_REFRESH_FILE, "r", encoding="utf-8") as f:
            last_refresh = float(f.read().strip())
    except (FileNotFoundError, ValueError):
        last_refresh = 0

    if now - last_refresh < TOKEN_REFRESH_INTERVAL_SECONDS:
        return

    print(
        "🔄 Threads: محاولة تجديد Access Token التلقائي..."
    )

    try:
        r = requests.get(
            f"{THREADS_API_BASE}/refresh_access_token",
            params={
                "grant_type": "th_refresh_token",
                "access_token": THREADS_ACCESS_TOKEN,
            },
            timeout=30,
        )

        if r.status_code != 200:
            print(
                f"⚠️ Threads Refresh Error: "
                f"{r.status_code} - {r.text[:500]}"
            )
            return

        data = r.json()
        new_token = data.get("access_token")

        if not new_token:
            print(
                "⚠️ Threads Refresh: لم يتم استلام توكن جديد."
            )
            return

        if update_github_secret("THREADS_ACCESS_TOKEN", new_token):
            THREADS_ACCESS_TOKEN = new_token
            with open(THREADS_REFRESH_FILE, "w", encoding="utf-8") as f:
                f.write(str(now))
            print(
                "✅ Threads: تم تجديد التوكن وتحديث "
                ".threads_token_refresh بنجاح."
            )

    except Exception as e:
        print(
            f"⚠️ Threads Refresh Connection Error: {e}"
        )


# =========================================================
# تصفير السجلات
# =========================================================

def reset_history_if_needed():
    """
    تُصفّر سجلات Facebook وInstagram وThreads كل 7 أيام.
    """
    now = time.time()

    try:
        with open(RESET_FILE, "r", encoding="utf-8") as f:
            last_reset = float(f.read().strip())
    except (FileNotFoundError, ValueError):
        last_reset = 0

    if now - last_reset >= HISTORY_RESET_SECONDS:
        for filename in (
            DB_FILE,
            IG_DB_FILE,
            THREADS_DB_FILE,
        ):
            with open(filename, "w", encoding="utf-8") as f:
                f.write("")

        with open(RESET_FILE, "w", encoding="utf-8") as f:
            f.write(str(now))

        print("🧹 تم تصفير سجلات Facebook وInstagram وThreads.")


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

    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"https?://(?:www\.)?t\.me/[A-Za-z0-9_+\-/?.=&%#]+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"(?<!\w)@Castlenewsiq\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

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

    text = re.sub(r"<[^>]+>", "", text)

    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.splitlines()
    ]

    return "\n".join(
        line for line in lines if line
    ).strip()


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
# Threads History
# =========================================================

def load_threads_history():
    try:
        with open(THREADS_DB_FILE, "r", encoding="utf-8") as f:
            return {
                line.strip()
                for line in f
                if line.strip()
            }
    except FileNotFoundError:
        return set()


def save_threads_history(msg_id):
    with open(THREADS_DB_FILE, "a", encoding="utf-8") as f:
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

    print(f"🌐 الاتصال بقناة: {SOURCE_CHANNEL}")

    res = requests.get(
        f"https://t.me/s/{SOURCE_CHANNEL}",
        headers=headers,
        timeout=20,
    )

    print(f"🔍 حالة الاستجابة: {res.status_code}")
    res.raise_for_status()

    items = re.findall(
        r'data-post="[^"/]+/(\d+)"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        res.text,
        re.DOTALL,
    )

    print(f"📊 عدد المنشورات المكتشفة: {len(items)}")

    return items[-limit:]


# =========================================================
# تحليل المنشور
# =========================================================

def is_album(item):
    """
    هل المنشور Album (رسائل مجمّعة)؟
    """
    return bool(
        re.search(
            r"tgme_widget_message_grouped|data-album=",
            item,
            flags=re.IGNORECASE,
        )
    )


def parse_album_item_anchor(anchor_html):
    """
    استخراج URL ونوع وسيط واحد داخل عنصر الـAlbum.
    """
    photo_match = re.search(
        r'background-image:url\([\'"]?([^\'")]+)',
        anchor_html,
        re.IGNORECASE,
    )

    if photo_match:
        return {
            "type": "photo",
            "url": html.unescape(photo_match.group(1)),
        }

    video_match = re.search(
        r'<video[^>]+(?:src|data-src)="([^"]+)"',
        anchor_html,
        re.IGNORECASE,
    )

    if not video_match:
        video_match = re.search(
            r'<source[^>]+src="([^"]+)"',
            anchor_html,
            re.IGNORECASE,
        )

    if video_match:
        return {
            "type": "video",
            "url": html.unescape(video_match.group(1)),
        }

    return None


def count_grouped_anchors(chunk):
    """
    عدّ عناصر الـAlbum داخل chunk المنشور على الصفحة الرئيسية.
    هذا العدد هو المرجع الحقيقي لعدد عناصر الـAlbum على Telegram.
    """
    anchors = re.findall(
        r'class="tgme_widget_message_photo_wrap grouped_media_wrap[^"]*"[^>]*>(.*?)</a>',
        chunk,
        re.DOTALL | re.IGNORECASE,
    )
    return len(anchors)


def parse_album(msg_id, item):
    """
    استخراج جميع عناصر الـAlbum بالترتيب الأصلي من المنشور.

    يرجع:
    - قائمة عناصر الـAlbum مع عددها الحقيقي
    - caption مشترك
    - الحالة (كامل/ناقص)

    لا يُعتبر الـAlbum الأكبر من 20 عنصرًا فشلًا:
    يتم اختيار أول MAX_ALBUM_ITEMS عنصر فقط.
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        )
    }

    try:
        res = requests.get(
            f"https://t.me/s/{SOURCE_CHANNEL}/{msg_id}",
            headers=headers,
            timeout=30,
        )

        if res.status_code != 200:
            print(
                f"⚠️ Album {msg_id}: "
                f"فشل جلب صفحة الرسالة ({res.status_code})."
            )
            return None

        page = res.text

    except Exception as e:
        print(
            f"⚠️ Album {msg_id}: "
            f"فشل الاتصال بصفحة الرسالة: {e}"
        )
        return None

    # -----------------------------------------------------
    # Locate grouped wrap بعد علامة رسالة الـAlbum
    # -----------------------------------------------------

    marker = re.search(
        rf'data-post="[^"]*{SOURCE_CHANNEL}/{msg_id}"',
        page,
        re.IGNORECASE,
    )

    if not marker:
        return None

    after = page[marker.start():]

    wrap_match = re.search(
        r'<div class="tgme_widget_message_grouped_wrap[^"]*"[^>]*>',
        after,
    )

    if not wrap_match:
        return None

    # -----------------------------------------------------
    # عناصر الـAlbum بالترتيب الأصلي
    # -----------------------------------------------------

    single_pattern = re.findall(
        r'class="tgme_widget_message_photo_wrap grouped_media_wrap[^"]*"'
        r'[^>]*background-image:url\(\s*[\'"]?([^\'"\)\s][^\'")\n]*)'
        r'[^>]*href="https://t\.me/[^"]+/(\d+)\?single"',
        after[wrap_match.start():],
        re.IGNORECASE,
    )

    if not single_pattern:
        return None

    expected_id = int(msg_id)
    items = []

    for url, href_id in single_pattern:
        if int(href_id) != expected_id:
            break

        items.append(
            {
                "type": "photo",
                "url": html.unescape(url),
            }
        )
        expected_id += 1

    # -----------------------------------------------------
    # حماية من Album ناقص
    # -----------------------------------------------------

    reference_count = count_grouped_anchors(item)

    print(
        f"🖼️ Album {msg_id}: "
        f"عدد العناصر في Telegram = {reference_count}، "
        f"المستخرجة = {len(items)}."
    )

    if len(items) < reference_count:
        print(
            f"❌ Album {msg_id}: "
            f"الاستخراج ناقص ({len(items)}/{reference_count}). "
            f"لن يُنشر، ويبقى قابلًا لإعادة المحاولة."
        )
        return None

    if reference_count == 0:
        return None

    # -----------------------------------------------------
    # الاختيار المركزي: أول MAX_ALBUM_ITEMS فقط
    # -----------------------------------------------------

    selected = items[:MAX_ALBUM_ITEMS]

    if len(items) > MAX_ALBUM_ITEMS:
        print(
            f"🔸 Album {msg_id}: "
            f"{len(items)} عنصر > {MAX_ALBUM_ITEMS}. "
            f"تم اختيار أول {MAX_ALBUM_ITEMS} عنصرًا فقط."
        )

    # -----------------------------------------------------
    # Caption مشترك من نص الرسالة
    # -----------------------------------------------------

    msg_match = re.search(
        r'class="tgme_widget_message_text[^>]*>(.*?)</div>',
        after,
        re.DOTALL | re.IGNORECASE,
    )

    raw_text = msg_match.group(1) if msg_match else ""
    caption = clean_news_text(raw_text)

    return {
        "id": str(msg_id),
        "type": "album",
        "items": selected,
        "caption": caption,
    }


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

    if re.search(
        r"tgme_widget_message_grouped|data-album=",
        item,
        flags=re.IGNORECASE,
    ):
        return None

    msg_match = re.search(
        r'class="tgme_widget_message_text[^>]*>(.*?)</div>',
        item,
        re.DOTALL | re.IGNORECASE,
    )

    raw_text = msg_match.group(1) if msg_match else ""
    caption = clean_news_text(raw_text)

    # -----------------------------------------------------
    # صورة منفردة
    # -----------------------------------------------------

    photo_match = re.search(
        r'tgme_widget_message_photo_wrap[^>]*style="[^"]*background-image:url\([\'"]?([^\'")]+)',
        item,
        re.IGNORECASE,
    )

    if photo_match:
        return {
            "id": str(msg_id),
            "type": "photo",
            "url": html.unescape(photo_match.group(1)),
            "caption": caption,
        }

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
                "url": html.unescape(img_match.group(1)),
                "caption": caption,
            }

    # -----------------------------------------------------
    # فيديو منفرد
    # -----------------------------------------------------

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
            "url": html.unescape(video_match.group(1)),
            "caption": caption,
        }

    return None


# =========================================================
# تنزيل الوسائط
# =========================================================

def download_media(media_url, media_type, msg_id):
    """
    تنزيل الوسيط مؤقتًا داخل GitHub Runner.
    """
    os.makedirs(
        TEMP_MEDIA_DIR,
        exist_ok=True,
    )

    ext = ".mp4" if media_type == "video" else ".jpg"

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

def check_facebook_token():
    """
    فحص صلاحية FB_TOKEN الدائمي الخاص بالصفحة قبل البدء.
    """
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print(
            "⚠️ Facebook: FB_PAGE_ID أو FB_TOKEN غير موجود."
        )
        return False

    print("🔎 Facebook: فحص Page Access Token...")

    try:
        r = requests.get(
            f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}",
            params={
                "fields": "id,name",
                "access_token": FB_PAGE_TOKEN,
            },
            timeout=30,
        )

        print(f"🔎 Facebook Token Status: {r.status_code}")

        if r.status_code != 200:
            print(
                f"❌ Facebook Token Error: "
                f"{r.status_code} - {r.text[:1000]}"
            )
            print(
                "⚠️ ملاحظة: توكن صفحة فيسبوك دائمي؛ "
                "إذا انتهت صلاحيته بسبب تغيير كلمة المرور أو الصلاحيات، "
                "يرجى تحديث FB_TOKEN يدوياً."
            )
            return False

        data = r.json()
        page_name = data.get("name") or "غير متوفر"
        print("✅ Facebook Page Token صالح (دائمي).")
        print(f"📘 Facebook Page: {page_name} ({FB_PAGE_ID})")
        return True

    except Exception as e:
        print(f"⚠️ Facebook Token Check Connection Error: {e}")
        return True


def post_to_facebook(
    media_path,
    media_type,
    message="",
):
    """
    مسار Facebook مستقل.
    """
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print(
            "⚠️ Facebook: FB_PAGE_ID أو FB_TOKEN غير موجود."
        )
        return False

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

            with open(media_path, "rb") as media_file:
                r = requests.post(
                    url,
                    data=payload,
                    files={"source": media_file},
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

            with open(media_path, "rb") as media_file:
                r = requests.post(
                    url,
                    data=payload,
                    files={"source": media_file},
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
            f"{r.status_code} - {r.text[:1000]}"
        )
        return False

    except Exception as e:
        print(
            f"⚠️ FB Connection Error: {e}"
        )
        return False


def post_album_to_facebook(
    media_paths,
    media_types,
    message="",
):
    """
    نشر الـAlbum على Facebook كمنشور واحد.
    """
    if not FB_PAGE_ID or not FB_PAGE_TOKEN:
        print(
            "⚠️ Facebook: FB_PAGE_ID أو FB_TOKEN غير موجود."
        )
        return False

    attached_media = []

    try:
        upload_url = (
            f"https://graph.facebook.com/v19.0/"
            f"{FB_PAGE_ID}/photos"
        )

        skipped_videos = 0

        for i, media_path in enumerate(media_paths):
            media_type = media_types[i]

            if media_type != "photo":
                skipped_videos += 1
                continue

            with open(media_path, "rb") as media_file:
                r = requests.post(
                    upload_url,
                    data={
                        "published": "false",
                        "access_token": FB_PAGE_TOKEN,
                    },
                    files={"source": media_file},
                    timeout=300,
                )

            if r.status_code != 200:
                print(
                    f"❌ Facebook: فشل رفع "
                    f"صورة {i + 1} - "
                    f"{r.status_code} - {r.text[:300]}"
                )
                return False

            try:
                media_fbid = r.json().get("id")
            except Exception:
                media_fbid = None

            if not media_fbid:
                print(
                    f"❌ Facebook: لم يتم استلام "
                    f"media_fbid لصورة {i + 1}."
                )
                return False

            attached_media.append(
                {"media_fbid": media_fbid}
            )

            print(
                f"✅ Facebook: تم رفع صورة "
                f"{i + 1}/{len(media_paths)} "
                f"({media_fbid})."
            )

        if skipped_videos > 0:
            print(
                f"🔸 Facebook: تم تخطي {skipped_videos} عنصرًا "
                f"من نوع فيديو - Facebook Graph API لا يدعم "
                f"نشر عدة فيديوهات في منشور واحد عبر "
                f"attached_media. لا سيتم تقسيم الـAlbum إلى "
                f"منشورات منفردة."
            )

        if not attached_media:
            print(
                "❌ Facebook: "
                "لا توجد صور صالحة للنشر."
            )
            if skipped_videos > 0:
                print(
                    "🔸 Facebook: الـAlbum يحتوي فيديوهات فقط - "
                    "لا مسار رسمي في Graph API يدعم نشر "
                    "فيديوهات متعددة كمنشور واحد. تم التخطي بأمان."
                )
            return False

        post_url = (
            f"https://graph.facebook.com/v19.0/"
            f"{FB_PAGE_ID}/feed"
        )

        print(
            f"📊 Facebook Album: selected="
            f"{len(attached_media)} attached="
            f"{len(attached_media)}"
        )

        payload = {
            "message": message,
            "access_token": FB_PAGE_TOKEN,
            "attached_media": (
                "[" + ",".join(
                    '{"media_fbid": "%s"}' % m["media_fbid"]
                    for m in attached_media
                ) + "]"
            ),
        }

        r = requests.post(
            post_url,
            data=payload,
            timeout=300,
        )

        if r.status_code == 200:
            note = ""
            if skipped_videos > 0:
                note = (
                    f" (تم تخطي {skipped_videos} عنصرًا من نوع "
                    f"فيديو بسبب عدم دعم Facebook له)"
                )
            print(
                f"✅ Facebook: تم نشر الـAlbum "
                f"({len(attached_media)} صور) كمنشور واحد"
                f"{note}."
            )
            return True

        print(
            f"❌ Facebook Album Error: "
            f"{r.status_code} - {r.text[:1000]}"
        )
        return False

    except Exception as e:
        print(
            f"⚠️ FB Album Connection Error: {e}"
        )
        return False


# =========================================================
# Instagram API
# =========================================================

def instagram_request(
    method,
    endpoint,
    **kwargs,
):
    """
    طلب مستقل إلى Instagram API.
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


def test_instagram_token():
    """
    التحقق من Instagram Token واستخراج User ID تلقائيًا.
    """
    global IG_USER_ID

    if not IG_ACCESS_TOKEN:
        print(
            "⚠️ Instagram: "
            "IG_ACCESS_TOKEN غير موجود."
        )
        return False

    print(
        "🔎 Instagram: فحص Access Token..."
    )

    r = instagram_request(
        "GET",
        "me",
        params={"fields": "id,username"},
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
            "❌ Instagram: تعذر قراءة استجابة Meta."
        )
        return False

    detected_id = data.get("id")
    username = data.get("username")

    if not detected_id:
        print(
            "❌ Instagram: Meta لم ترجع User ID."
        )
        print(f"📋 Response: {data}")
        return False

    IG_USER_ID = str(detected_id)

    print("✅ Instagram Token صالح.")
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
    album_items=None,
):
    """
    نشر صورة أو فيديو على Instagram.

    يدعم أيضًا الـAlbum كـCarousel واحد
    عبر album_items (قائمة عناصر {type, url}).
    """
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        return False

    caption = (caption or "")[:2200]

    # -----------------------------------------------------
    # Instagram Carousel (Album)
    # -----------------------------------------------------

    if album_items:
        ig_items = album_items[:MAX_ALBUM_ITEMS]

        if len(album_items) > MAX_ALBUM_ITEMS:
            print(
                f"🔸 Instagram: تم اختيار أول "
                f"{MAX_ALBUM_ITEMS} عنصرًا من أصل "
                f"{len(album_items)} "
                f"(بقية العناصر لن تُنشر)."
            )

        creation_ids = []

        for i, ig_item in enumerate(ig_items):
            item_type = ig_item["type"]
            item_url = ig_item["url"]

            if item_type == "photo":
                payload = {
                    "image_url": item_url,
                    "is_carousel_item": True,
                }

            elif item_type == "video":
                payload = {
                    "media_type": "VIDEO",
                    "video_url": item_url,
                    "is_carousel_item": True,
                }

            else:
                continue

            print(
                f"📡 Instagram Carousel: إنشاء "
                f"Container {i + 1}/{len(ig_items)}..."
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
                    f"❌ Instagram Carousel Container "
                    f"Error ({i + 1}): "
                    f"{r.status_code} - {r.text[:500]}"
                )
                return False

            try:
                cid = r.json().get("id")
            except Exception:
                cid = None

            if not cid:
                print(
                    "❌ Instagram: لم يتم استلام "
                    "creation_id لـContainer."
                )
                return False

            creation_ids.append(cid)

            print(
                f"🆔 Instagram Carousel Container "
                f"{i + 1}: {cid}"
            )

        if not creation_ids:
            print(
                "❌ Instagram: "
                "لا توجد عناصر صالحة للـCarousel."
            )
            return False

        print(
            "⏳ Instagram: انتظار تجهيز "
            "عناصر الـCarousel..."
        )

        max_checks = 30

        for attempt in range(max_checks):
            time.sleep(5)

            ready = True
            any_failed = False

            for cid in creation_ids:
                status = instagram_request(
                    "GET",
                    cid,
                    params={
                        "fields": "status_code"
                    },
                )

                if status is None:
                    ready = False
                    continue

                if status.status_code != 200:
                    continue

                try:
                    data = status.json()
                except Exception:
                    data = {}

                status_code = str(
                    data.get("status_code", "")
                ).upper()

                if status_code == "FINISHED":
                    continue

                if status_code in {"ERROR", "EXPIRED"}:
                    print(
                        "❌ Instagram: فشل تجهيز "
                        "أحد عناصر الـCarousel."
                    )
                    any_failed = True
                    break

                ready = False

            if any_failed:
                return False

            if ready:
                print(
                    "✅ Instagram: "
                    "تم تجهيز جميع عناصر الـCarousel."
                )
                break

            print(
                f"⏳ Instagram: انتظار "
                f"({attempt + 1}/{max_checks})"
            )

        else:
            print(
                "❌ Instagram: "
                "انتهت مهلة تجهيز عناصر الـCarousel."
            )
            return False

        if len(creation_ids) != len(ig_items):
            print(
                f"❌ Instagram Carousel: عدد العناصر "
                f"الجاهزة ({len(creation_ids)}) لا يساوي "
                f"عدد العناصر المختارة ({len(ig_items)}). "
                f"لا نشر ولا History - إعادة المحاولة لاحقًا."
            )
            return False

        print(
            f"📊 Instagram Carousel: selected="
            f"{len(ig_items)} children={len(creation_ids)}"
        )

        print(
            "📦 Instagram: إنشاء Parent Carousel..."
        )

        parent = instagram_request(
            "POST",
            f"{IG_USER_ID}/media",
            data={
                "media_type": "CAROUSEL",
                "caption": caption,
                "children": ",".join(creation_ids),
            },
        )

        if parent is None or parent.status_code != 200:
            if parent is not None:
                print(
                    f"❌ Instagram Parent Carousel Error: "
                    f"{parent.status_code} - "
                    f"{parent.text[:1000]}"
                )
            return False

        try:
            parent_id = parent.json().get("id")
        except Exception:
            parent_id = None

        if not parent_id:
            print(
                "❌ Instagram: لم يتم استلام Parent Carousel ID."
            )
            return False

        print(
            f"🆔 Instagram Parent Carousel: {parent_id}"
        )

        parent_ready = False
        for attempt in range(max_checks):
            time.sleep(5)

            status = instagram_request(
                "GET",
                parent_id,
                params={
                    "fields": "status_code,status"
                },
            )

            if status is None or status.status_code != 200:
                continue

            try:
                data = status.json()
            except Exception:
                data = {}

            status_code = str(
                data.get("status_code", "")
            ).upper()

            if status_code == "FINISHED":
                parent_ready = True
                print(
                    "✅ Instagram: Parent Carousel جاهز."
                )
                break

            if status_code in {"ERROR", "EXPIRED"}:
                print(
                    "❌ Instagram: فشل تجهيز Parent Carousel."
                )
                print(f"📋 التفاصيل: {data}")
                return False

            print(
                f"⏳ Instagram: انتظار تجهيز Parent "
                f"({attempt + 1}/{max_checks}) - "
                f"{status_code or 'PROCESSING'}"
            )

        if not parent_ready:
            print(
                "❌ Instagram: انتهت مهلة تجهيز Parent Carousel."
            )
            return False

        print(
            "📤 Instagram: نشر Parent Carousel..."
        )

        publish = instagram_request(
            "POST",
            f"{IG_USER_ID}/media_publish",
            data={"creation_id": parent_id},
        )

        if publish is None:
            return False

        if publish.status_code == 200:
            try:
                published_id = publish.json().get("id")
            except Exception:
                published_id = None
            print(
                "✅ Instagram: تم نشر الـCarousel "
                f"(منشور واحد) بنجاح. ID={published_id or 'غير متوفر'}"
            )
            return True

        print(
            f"❌ Instagram Carousel Publish Error: "
            f"{publish.status_code} - "
            f"{publish.text[:1000]}"
        )
        return False

    # -----------------------------------------------------
    # صورة أو فيديو منفرد (المسار الحالي)
    # -----------------------------------------------------

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
            f"{r.status_code} - {r.text[:1000]}"
        )
        return False

    try:
        creation_id = r.json().get("id")
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

    max_checks = (
        60 if media_type == "video" else 20
    )

    for attempt in range(max_checks):
        time.sleep(5)

        status = instagram_request(
            "GET",
            creation_id,
            params={
                "fields": "status_code,status"
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
            data.get("status_code", "")
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
            print(f"📋 التفاصيل: {data}")
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

    print(
        "📤 Instagram: نشر الـ Container..."
    )

    publish = instagram_request(
        "POST",
        f"{IG_USER_ID}/media_publish",
        data={"creation_id": creation_id},
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
# Threads API
# =========================================================

def threads_request(
    method,
    endpoint,
    **kwargs,
):
    """
    طلب مستقل إلى Threads API.

    يستخدم:
    https://graph.threads.net
    مع Threads User Access Token.
    """
    if not THREADS_ACCESS_TOKEN:
        print(
            "⚠️ Threads: "
            "THREADS_ACCESS_TOKEN غير موجود."
        )
        return None

    url = (
        f"{THREADS_API_BASE}/"
        f"{endpoint.lstrip('/')}"
    )

    headers = kwargs.pop(
        "headers",
        {},
    )

    headers["Authorization"] = (
        f"Bearer {THREADS_ACCESS_TOKEN}"
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
            f"⚠️ Threads Connection Error: {e}"
        )
        return None


def test_threads_token():
    """
    فحص Threads Access Token واستخراج Threads User ID
    من /me تلقائيًا.
    """
    global THREADS_USER_ID

    if not THREADS_ACCESS_TOKEN:
        print(
            "⚠️ Threads: "
            "THREADS_ACCESS_TOKEN غير موجود."
        )
        return False

    print(
        "🔎 Threads: فحص Access Token..."
    )

    r = threads_request(
        "GET",
        "me",
        params={
            "fields": "id,username"
        },
    )

    if r is None:
        return False

    print(
        f"🔎 Threads Token Status: "
        f"{r.status_code}"
    )

    if r.status_code != 200:
        print(
            "❌ Threads Token Error: "
            f"{r.text[:1000]}"
        )
        return False

    try:
        data = r.json()
    except Exception:
        print(
            "❌ Threads: "
            "تعذر قراءة استجابة Meta."
        )
        return False

    detected_id = data.get("id")
    username = data.get("username")

    if not detected_id:
        print(
            "❌ Threads: "
            "Meta لم ترجع User ID."
        )
        print(f"📋 Response: {data}")
        return False

    THREADS_USER_ID = str(detected_id)

    print(
        "✅ Threads Token صالح."
    )
    print(
        f"👤 Threads Username: "
        f"{username or 'غير متوفر'}"
    )
    print(
        f"🆔 Threads User ID: "
        f"{THREADS_USER_ID}"
    )

    return True


def post_to_threads(
    media_url,
    media_type,
    caption="",
    album_items=None,
):
    """
    نشر صورة أو فيديو على Threads.

    Threads API:
    1) إنشاء Media Container
    2) انتظار تجهيز الفيديو عند الحاجة
    3) نشر Container
    """
    if not THREADS_USER_ID:
        print(
            "⚠️ Threads: "
            "THREADS_USER_ID غير موجود."
        )
        return False

    if not THREADS_ACCESS_TOKEN:
        print(
            "⚠️ Threads: "
            "THREADS_ACCESS_TOKEN غير موجود."
        )
        return False

    # Threads يدعم 500 حرف للنص الرئيسي.
    caption = (caption or "")[:500]

    # -----------------------------------------------------
    # Threads Carousel (Album)
    # -----------------------------------------------------

    if album_items:
        th_items = album_items[:20]

        creation_ids = []

        for i, th_item in enumerate(th_items):
            item_type = th_item["type"]
            item_url = th_item["url"]

            if item_type == "photo":
                payload = {
                    "media_type": "IMAGE",
                    "image_url": item_url,
                    "is_carousel_item": True,
                }

            elif item_type == "video":
                payload = {
                    "media_type": "VIDEO",
                    "video_url": item_url,
                    "is_carousel_item": True,
                }

            else:
                continue

            print(
                f"📡 Threads Carousel: إنشاء "
                f"Container {i + 1}/{len(th_items)}..."
            )

            r = threads_request(
                "POST",
                "me/threads",
                data=payload,
            )

            if r is None:
                return False

            if r.status_code != 200:
                print(
                    f"❌ Threads Carousel Container "
                    f"Error ({i + 1}): "
                    f"{r.status_code} - {r.text[:500]}"
                )
                return False

            try:
                cid = r.json().get("id")
            except Exception:
                cid = None

            if not cid:
                print(
                    "❌ Threads: لم يتم استلام "
                    "Container ID."
                )
                return False

            creation_ids.append(cid)

            print(
                f"🆔 Threads Carousel Container "
                f"{i + 1}: {cid}"
            )

        if not creation_ids:
            print(
                "❌ Threads: "
                "لا توجد عناصر صالحة للـCarousel."
            )
            return False

        print(
            "⏳ Threads: انتظار تجهيز "
            "عناصر الـCarousel..."
        )

        max_checks = 30

        for attempt in range(max_checks):
            time.sleep(5)

            ready = True
            any_failed = False

            for cid in creation_ids:
                status = threads_request(
                    "GET",
                    cid,
                    params={
                        "fields": "status,error_message"
                    },
                )

                if status is None:
                    ready = False
                    continue

                if status.status_code != 200:
                    continue

                try:
                    data = status.json()
                except Exception:
                    data = {}

                status_value = str(
                    data.get("status", "")
                ).upper()

                if status_value in {"FINISHED", "PUBLISHED"}:
                    continue

                if status_value in {"ERROR", "EXPIRED"}:
                    print(
                        "❌ Threads: فشل تجهيز "
                        "أحد عناصر الـCarousel."
                    )
                    any_failed = True
                    break

                ready = False

            if any_failed:
                return False

            if ready:
                print(
                    "✅ Threads: "
                    "تم تجهيز جميع عناصر الـCarousel."
                )
                break

            print(
                f"⏳ Threads: انتظار "
                f"({attempt + 1}/{max_checks})"
            )

        else:
            print(
                "❌ Threads: "
                "انتهت مهلة تجهيز عناصر الـCarousel."
            )
            return False

        if len(creation_ids) != len(th_items):
            print(
                f"❌ Threads Carousel: عدد العناصر "
                f"الجاهزة ({len(creation_ids)}) لا يساوي "
                f"عدد العناصر المختارة ({len(th_items)}). "
                f"لا نشر ولا History - إعادة المحاولة لاحقًا."
            )
            return False

        print(
            f"📊 Threads Carousel: selected="
            f"{len(th_items)} children={len(creation_ids)}"
        )

        print(
            "📦 Threads: إنشاء Parent Carousel..."
        )

        parent = threads_request(
            "POST",
            "me/threads",
            data={
                "text": caption,
                "media_type": "CAROUSEL",
                "children": ",".join(creation_ids),
            },
        )

        if parent is None or parent.status_code != 200:
            if parent is not None:
                print(
                    f"❌ Threads Parent Carousel Error: "
                    f"{parent.status_code} - "
                    f"{parent.text[:1000]}"
                )
            return False

        try:
            parent_id = parent.json().get("id")
        except Exception:
            parent_id = None

        if not parent_id:
            print(
                "❌ Threads: لم يتم استلام Parent Carousel ID."
            )
            return False

        print(
            f"🆔 Threads Parent Carousel: {parent_id}"
        )

        parent_ready = False
        for attempt in range(max_checks):
            time.sleep(5)

            status = threads_request(
                "GET",
                parent_id,
                params={
                    "fields": "status,error_message"
                },
            )

            if status is None or status.status_code != 200:
                continue

            try:
                data = status.json()
            except Exception:
                data = {}

            status_value = str(
                data.get("status", "")
            ).upper()

            if status_value in {"FINISHED", "PUBLISHED"}:
                parent_ready = True
                print(
                    "✅ Threads: Parent Carousel جاهز."
                )
                break

            if status_value in {"ERROR", "EXPIRED"}:
                print(
                    "❌ Threads: فشل تجهيز Parent Carousel."
                )
                print(f"📋 التفاصيل: {data}")
                return False

            print(
                f"⏳ Threads: انتظار تجهيز Parent "
                f"({attempt + 1}/{max_checks}) - "
                f"{status_value or 'PROCESSING'}"
            )

        if not parent_ready:
            print(
                "❌ Threads: انتهت مهلة تجهيز Parent Carousel."
            )
            return False

        print(
            "📤 Threads: نشر Parent Carousel..."
        )

        publish = threads_request(
            "POST",
            "me/threads_publish",
            data={"creation_id": parent_id},
        )

        if publish is None:
            return False

        if publish.status_code == 200:
            try:
                published_id = publish.json().get("id")
            except Exception:
                published_id = None
            print(
                "✅ Threads: تم نشر الـCarousel "
                f"(منشور واحد) بنجاح. ID={published_id or 'غير متوفر'}"
            )
            return True

        print(
            f"❌ Threads Carousel Publish Error: "
            f"{publish.status_code} - "
            f"{publish.text[:1000]}"
        )
        return False

    # -----------------------------------------------------
    # صورة أو فيديو منفرد (المسار الحالي)
    # -----------------------------------------------------

    if media_type == "photo":
        payload = {
            "text": caption,
            "media_type": "IMAGE",
            "image_url": media_url,
        }

    elif media_type == "video":
        payload = {
            "text": caption,
            "media_type": "VIDEO",
            "video_url": media_url,
        }

    else:
        return False

    print(
        f"📡 Threads: إنشاء Container "
        f"للـ {media_type}..."
    )

    r = threads_request(
        "POST",
        "me/threads",
        data=payload,
    )

    if r is None:
        return False

    if r.status_code != 200:
        print(
            f"❌ Threads Container Error: "
            f"{r.status_code} - "
            f"{r.text[:1000]}"
        )
        return False

    try:
        creation_id = r.json().get("id")
    except Exception:
        creation_id = None

    if not creation_id:
        print(
            "❌ Threads: "
            "لم يتم استلام Container ID."
        )
        print(
            f"📋 Response: {r.text[:1000]}"
        )
        return False

    print(
        f"🆔 Threads Container: "
        f"{creation_id}"
    )

    max_checks = 60 if media_type == "video" else 10

    for attempt in range(max_checks):
        time.sleep(5)

        status = threads_request(
            "GET",
            creation_id,
            params={
                "fields": "status,error_message"
            },
        )

        if status is None:
            continue

        if status.status_code != 200:
            print(
                f"⚠️ Threads Status Error: "
                f"{status.status_code} - "
                f"{status.text[:500]}"
            )
            continue

        try:
            data = status.json()
        except Exception:
            data = {}

        status_value = str(
            data.get("status", "")
        ).upper()

        if status_value in {
            "FINISHED",
            "PUBLISHED",
        }:
            print(
                "✅ Threads: "
                "تم تجهيز الـ Container."
            )
            break

        if status_value in {
            "ERROR",
            "EXPIRED",
        }:
            print(
                "❌ Threads: "
                "فشل تجهيز الوسائط."
            )
            print(
                f"📋 التفاصيل: {data}"
            )
            return False

        if (
            media_type == "photo"
            and not status_value
        ):
            print(
                "✅ Threads: "
                "الصورة جاهزة للنشر."
            )
            break

        print(
            f"⏳ Threads: انتظار معالجة "
            f"{media_type} "
            f"({attempt + 1}/{max_checks}) - "
            f"{status_value or 'IN_PROGRESS'}"
        )

    else:
        print(
            "❌ Threads: "
            "انتهت مهلة انتظار معالجة الوسائط."
        )
        return False

    # -----------------------------------------------------
    # نشر Container
    # -----------------------------------------------------

    print(
        "📤 Threads: نشر الـ Container..."
    )

    publish = threads_request(
        "POST",
        "me/threads_publish",
        data={
            "creation_id": creation_id
        },
    )

    if publish is None:
        return False

    if publish.status_code == 200:
        print(
            f"✅ Threads: تم نشر "
            f"{media_type} بنجاح"
        )

        try:
            published_id = publish.json().get("id")
            if published_id:
                print(
                    f"🆔 Threads Post ID: "
                    f"{published_id}"
                )
        except Exception:
            pass

        return True

    print(
        f"❌ Threads Publish Error: "
        f"{publish.status_code} - "
        f"{publish.text[:1000]}"
    )

    return False


# =========================================================
# حذف الملفات المؤقتة
# =========================================================

def remove_temp_file(path):
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

    if not is_work_time():
        print(
            "🌙 خارج وقت العمل."
        )
        return

    # -----------------------------------------------------
    # تجديد التوكنات التلقائي كل 45 يوماً (Instagram & Threads)
    # -----------------------------------------------------

    refresh_instagram_token_if_needed()
    refresh_threads_token_if_needed()

    # -----------------------------------------------------
    # فحص Facebook
    # -----------------------------------------------------

    check_facebook_token()

    # -----------------------------------------------------
    # فحص Instagram
    # -----------------------------------------------------

    instagram_ready = test_instagram_token()

    if not instagram_ready:
        print(
            "⚠️ Instagram: "
            "فشل فحص Token."
        )
        print(
            "⚠️ سيتم الاستمرار في Facebook وThreads."
        )

    # -----------------------------------------------------
    # فحص Threads
    # -----------------------------------------------------

    threads_ready = test_threads_token()

    if not threads_ready:
        print(
            "⚠️ Threads: "
            "فشل فحص Token."
        )
        print(
            "⚠️ سيتم الاستمرار في Facebook وInstagram."
        )

    # -----------------------------------------------------
    # History
    # -----------------------------------------------------

    reset_history_if_needed()
    cleanup_temp_dir()

    fb_history = load_history()
    ig_history = load_instagram_history()
    threads_history = load_threads_history()

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

        # الأقدم أولًا ضمن آخر 10
        for msg_id, item in items:
            sig = msg_id.strip()

            # إذا نجح على المنصات الثلاث سابقًا
            if (
                sig in fb_history
                and sig in ig_history
                and sig in threads_history
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

            album = None

            if not post and is_album(item):
                album = parse_album(sig, item)

            # -------------------------------------------------
            # تجاهل النصوص والأنواع غير المدعومة
            # -------------------------------------------------

            if not post and not album:
                print(
                    f"⏭️ تجاهل المنشور "
                    f"{sig}: نص فقط أو "
                    f"نوع غير مدعوم."
                )

                if sig not in fb_history:
                    save_history(sig)
                    fb_history.add(sig)

                if sig not in ig_history:
                    save_instagram_history(sig)
                    ig_history.add(sig)

                if sig not in threads_history:
                    save_threads_history(sig)
                    threads_history.add(sig)

                continue

            temp_paths = []

            try:
                # =============================================
                # Album: تنزيل الوسائط مرة واحدة فقط
                # =============================================

                if album:
                    print(
                        f"🖼️ Album {sig}: "
                        f"{len(album['items'])} عنصر - "
                        f"يُنشر كمنشور واحد على كل منصة."
                    )

                    for i, album_item in enumerate(
                        album["items"]
                    ):
                        temp_path = download_media(
                            album_item["url"],
                            album_item["type"],
                            f"{sig}_{i}",
                        )

                        temp_paths.append(temp_path)

                # =============================================
                # Facebook
                # =============================================

                if sig not in fb_history:
                    if album:
                        fb_success = (
                            post_album_to_facebook(
                                temp_paths,
                                [
                                    it["type"]
                                    for it in
                                    album["items"]
                                ],
                                album["caption"],
                            )
                        )
                    else:
                        print(
                            f"📘 Facebook: معالجة "
                            f"{post['type']}..."
                        )

                        temp_path = download_media(
                            post["url"],
                            post["type"],
                            sig,
                        )

                        temp_paths.append(temp_path)

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
                            "لكن سيستمر Instagram وThreads."
                        )

                # =============================================
                # Instagram
                # =============================================

                if (
                    instagram_ready
                    and sig not in ig_history
                ):
                    if album:
                        ig_success = (
                            post_to_instagram(
                                "",
                                "photo",
                                album["caption"],
                                album_items=(
                                    album["items"]
                                ),
                            )
                        )
                    else:
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
                        save_instagram_history(sig)
                        ig_history.add(sig)
                        print(
                            "💾 Instagram: "
                            "تم حفظ المعرف بنجاح."
                        )
                    else:
                        print(
                            "⚠️ Instagram: "
                            "فشل النشر، "
                            "ولا يؤثر ذلك على Facebook وThreads."
                        )

                elif not instagram_ready:
                    print(
                        "⏭️ Instagram: "
                        "تم تخطيه بسبب فشل المصادقة."
                    )

                # =============================================
                # Threads
                # =============================================

                if (
                    threads_ready
                    and sig not in threads_history
                ):
                    if album:
                        threads_success = (
                            post_to_threads(
                                "",
                                "photo",
                                album["caption"],
                                album_items=(
                                    album["items"]
                                ),
                            )
                        )
                    else:
                        print(
                            f"🧵 Threads: معالجة "
                            f"{post['type']}..."
                        )

                        threads_success = post_to_threads(
                            post["url"],
                            post["type"],
                            post["caption"],
                        )

                    if threads_success:
                        save_threads_history(sig)
                        threads_history.add(sig)
                        print(
                            "💾 Threads: "
                            "تم حفظ المعرف بنجاح."
                        )
                    else:
                        print(
                            "⚠️ Threads: "
                            "فشل النشر، "
                            "ولا يؤثر ذلك على Facebook وInstagram."
                        )

                elif not threads_ready:
                    print(
                        "⏭️ Threads: "
                        "تم تخطيه بسبب فشل المصادقة."
                    )

                # =============================================
                # Cleanup: حذف الملفات المؤقتة بعد انتهاء
                # المنصات الثلاث جميعًا
                # =============================================

                for temp_path in temp_paths:
                    remove_temp_file(temp_path)

                temp_paths.clear()

            except Exception as e:
                print(
                    f"⚠️ خطأ في المنشور "
                    f"{sig}: {e}"
                )

                for temp_path in temp_paths:
                    remove_temp_file(temp_path)

                temp_paths.clear()

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
