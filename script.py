import os
import re
import html
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')
DB_FILE = "last_news_id.txt"
RESET_FILE = ".news_history_reset"
SOURCE_CHANNEL = 'Castlenewsiq'

# الحد الأقصى 5 منشورات في كل تشغيل (كل ساعتين)
MAX_POSTS_PER_RUN = 5
POST_DELAY_SECONDS = 10
HISTORY_RESET_SECONDS = 48 * 60 * 60
TEMP_MEDIA_DIR = "tmp_media"


def is_work_time():
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23


def reset_history_if_needed():
    """تصفير سجل الأخبار كل 48 ساعة مع حفظ وقت آخر تصفير."""
    now = time.time()
    try:
        with open(RESET_FILE, 'r', encoding='utf-8') as f:
            last_reset = float(f.read().strip())
    except (FileNotFoundError, ValueError):
        last_reset = 0

    if now - last_reset >= HISTORY_RESET_SECONDS:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            f.write('')
        with open(RESET_FILE, 'w', encoding='utf-8') as f:
            f.write(str(now))
        print("🧹 تم تصفير سجل الأخبار.")


def clean_news_text(text):
    """تنظيف Caption وحذف روابط القناة من المنشور."""
    if not text:
        return ""

    text = html.unescape(text)

    # تحويل BR إلى أسطر قبل إزالة بقية HTML.
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

    # حذف روابط Telegram كاملة سواء كانت http أو https.
    text = re.sub(
        r'https?://(?:www\.)?t\.me/[A-Za-z0-9_+\-/?.=&%#]+',
        '',
        text,
        flags=re.IGNORECASE,
    )

    # حذف @Castlenewsiq إذا ظهر داخل النص.
    text = re.sub(r'(?<!\w)@Castlenewsiq\b', '', text, flags=re.IGNORECASE)

    # حذف توقيع القناة المعروف حتى لو تغير تنسيق الأسطر قليلًا.
    text = re.sub(
        r'للمزيد\s*من\s*الأخبار\s*اشترك\s*في\s*قناتنا\s*:?\s*👇?',
        '',
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r'اشترك\s*في\s*قناتنا\s*:?\s*👇?',
        '',
        text,
        flags=re.IGNORECASE,
    )

    # إزالة بقية وسوم HTML.
    text = re.sub(r'<[^>]+>', '', text)

    # تنظيف الفراغات والأسطر الزائدة.
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()]
    text = '\n'.join(line for line in lines if line)
    return text.strip()


def load_history():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


def save_history(msg_id):
    with open(DB_FILE, 'a', encoding='utf-8') as f:
        f.write(f'{msg_id}\n')


def fetch_latest_posts(limit=MAX_POSTS_PER_RUN):
    """جلب آخر منشورات القناة بالطريقة الحالية نفسها."""
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/151.0 Safari/537.36'
        )
    }

    print(f"🌐 الاتصال بقناة: {SOURCE_CHANNEL}")
    res = requests.get(
        f'https://t.me/s/{SOURCE_CHANNEL}',
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


def parse_post(msg_id, item):
    """تحديد صورة/فيديو منفرد فقط؛ النصوص وAlbums يتم تجاهلها."""
    # Album / grouped media: تجاهل كامل.
    if re.search(
        r'tgme_widget_message_grouped|data-album=',
        item,
        flags=re.IGNORECASE,
    ):
        return None

    # استخراج Caption.
    msg_match = re.search(
        r'class="tgme_widget_message_text[^>]*>(.*?)</div>',
        item,
        re.DOTALL | re.IGNORECASE,
    )
    raw_text = msg_match.group(1) if msg_match else ''
    caption = clean_news_text(raw_text)

    # صورة منفردة: Telegram غالبًا يضع الرابط في background-image.
    photo_match = re.search(
        r'tgme_widget_message_photo_wrap[^>]*style="[^"]*background-image:url\([\'\"]?([^\'\")]+)',
        item,
        re.IGNORECASE,
    )
    if photo_match:
        return {
            'id': str(msg_id),
            'type': 'photo',
            'url': html.unescape(photo_match.group(1)),
            'caption': caption,
        }

    # fallback للصورة إذا ظهر src مباشر.
    if re.search(r'tgme_widget_message_photo_wrap', item, re.IGNORECASE):
        img_match = re.search(r'<img[^>]+src="([^"]+)"', item, re.IGNORECASE)
        if img_match:
            return {
                'id': str(msg_id),
                'type': 'photo',
                'url': html.unescape(img_match.group(1)),
                'caption': caption,
            }

    # فيديو منفرد.
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
            'id': str(msg_id),
            'type': 'video',
            'url': html.unescape(video_match.group(1)),
            'caption': caption,
        }

    # أي منشور بدون صورة/فيديو = نص فقط أو نوع غير مدعوم.
    return None


def download_media(media_url, media_type, msg_id):
    """تنزيل الوسيط مؤقتًا داخل Runner فقط."""
    os.makedirs(TEMP_MEDIA_DIR, exist_ok=True)
    ext = '.mp4' if media_type == 'video' else '.jpg'
    path = os.path.join(TEMP_MEDIA_DIR, f'{msg_id}{ext}')

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/151.0 Safari/537.36'
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
            with open(path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
        return path
    except Exception:
        remove_temp_file(path)
        raise


def post_to_facebook(media_path, media_type, message=''):
    """رفع صورة أو فيديو إلى Facebook؛ لا يوجد نشر نص فقط."""
    try:
        if media_type == 'photo':
            url = f'https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos'
            payload = {
                'caption': message,
                'access_token': FB_PAGE_TOKEN,
            }
            with open(media_path, 'rb') as media_file:
                r = requests.post(
                    url,
                    data=payload,
                    files={'source': media_file},
                    timeout=120,
                )
        else:
            url = f'https://graph.facebook.com/v19.0/{FB_PAGE_ID}/videos'
            payload = {
                'description': message,
                'access_token': FB_PAGE_TOKEN,
            }
            with open(media_path, 'rb') as media_file:
                r = requests.post(
                    url,
                    data=payload,
                    files={'source': media_file},
                    timeout=300,
                )

        if r.status_code == 200:
            print(f"✅ Facebook: تم نشر {media_type} بنجاح")
            return True

        print(f"❌ Facebook Error: {r.status_code} - {r.text[:500]}")
        return False
    except Exception as e:
        print(f"⚠️ FB Connection Error: {e}")
        return False


def remove_temp_file(path):
    """حذف الملف سواء نجح النشر أو فشل."""
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"🗑️ تم حذف الملف المؤقت: {path}")
    except OSError as e:
        print(f"⚠️ تعذر حذف الملف المؤقت {path}: {e}")


def cleanup_temp_dir():
    try:
        if not os.path.isdir(TEMP_MEDIA_DIR):
            return
        for name in os.listdir(TEMP_MEDIA_DIR):
            remove_temp_file(os.path.join(TEMP_MEDIA_DIR, name))
        try:
            os.rmdir(TEMP_MEDIA_DIR)
        except OSError:
            pass
    except OSError as e:
        print(f"⚠️ خطأ بتنظيف مجلد الوسائط: {e}")


def main():
    print("🚀 بدء تنفيذ البوت...")

    if not is_work_time():
        print("🌙 خارج وقت العمل.")
        return

    # تصفير السجل كل 48 ساعة.
    reset_history_if_needed()
    cleanup_temp_dir()

    history = load_history()

    try:
        items = fetch_latest_posts(MAX_POSTS_PER_RUN)

        if not items:
            print("⚠️ تنبيه: لم يتم العثور على أي منشورات.")
            return

        # الأقدم أولًا ضمن آخر 5، حتى يبقى ترتيب النشر طبيعيًا.
        for msg_id, item in items:
            sig = msg_id.strip()
            if sig in history:
                continue

            print(f"📌 فحص المنشور رقم: {sig}")
            post = parse_post(sig, item)

            # النصوص فقط وAlbums لا يتم نشرها.
            if not post:
                print(f"⏭️ تجاهل المنشور {sig}: نص فقط أو Album/نوع غير مدعوم.")
                save_history(sig)
                history.add(sig)
                continue

            temp_path = None
            try:
                print(f"📦 نوع المنشور: {post['type']}")
                temp_path = download_media(post['url'], post['type'], sig)

                success = post_to_facebook(
                    temp_path,
                    post['type'],
                    post['caption'],
                )

                if success:
                    save_history(sig)
                    history.add(sig)
                    print("💾 تم حفظ المعرف بنجاح.")
                else:
                    print("⚠️ فشل النشر، وسيبقى المعرف غير محفوظ لإتاحة المحاولة لاحقًا.")

            except Exception as e:
                print(f"⚠️ خطأ في المنشور {sig}: {e}")

            finally:
                # الحذف دائمًا، سواء نجح النشر أو فشل.
                remove_temp_file(temp_path)

            # 10 ثوانٍ بين المنشورات التي تتم معالجتها.
            time.sleep(POST_DELAY_SECONDS)

    except Exception as e:
        print(f"⚠️ خطأ عام: {e}")

    finally:
        # تنظيف إضافي قبل انتهاء Runner.
        cleanup_temp_dir()


if __name__ == '__main__':
    main()
