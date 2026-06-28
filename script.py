import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')
DB_FILE = "last_news_id.txt"
SOURCE_CHANNEL = 'Castlenewsiq'

def is_work_time():
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def clean_news_text(text):
    if not text:
        return ""
    # تنظيف الرابط الخاص بالقناة
    text = re.sub(r'للمزيد\s*من\s*الأخبار\s*اشترك\s*في\s*قناتنا:\s*👇\s*\n?https://t\.me/Castlenewsiq', '', text)
    # تنظيف الفراغات الزائدة
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

def post_to_facebook(message):
    if not message:
        print("⚠️ النص فارغ، لا يمكن النشر.")
        return False
        
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
        r = requests.post(url, data=payload, timeout=15)
        
        if r.status_code == 200:
            return True
        else:
            print(f"❌ رفض من فيسبوك (الكود {r.status_code}): {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ FB Error: {e}")
        return False

def main():
    print("🚀 بدء تنفيذ البوت لفحص آخر 5 منشورات...")
    if not is_work_time():
        print("🌙 خارج وقت العمل.")
        return

    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        res = requests.get(f"https://t.me/s/{SOURCE_CHANNEL}", headers=headers, timeout=15)
        
        # الطريقة الجديدة: تقطيع الصفحة جراحياً لضمان جلب المنشورات
        chunks = res.text.split('data-post="')[1:]
        matches = []
        
        for chunk in chunks:
            # جلب المعرف
            id_match = re.match(r'[^"]+/(\d+)"', chunk)
            if id_match:
                msg_id = id_match.group(1)
                # جلب النص الخاص بهذا المعرف فقط
                text_match = re.search(r'class="tgme_widget_message_text[^"]*">(.*?)</div>', chunk, re.DOTALL)
                if text_match:
                    matches.append((msg_id, text_match.group(1)))

        print(f"📊 تم العثور على {len(matches)} منشور نصي في الصفحة.")

        if not matches:
            print("⚠️ لم يتم العثور على أي منشور، تأكد من القناة.")
            return

        for msg_id, raw_html_text in reversed(matches[-5:]):
            sig = msg_id.strip()
            
            if sig in history:
                print(f"⏭️ المنشور {sig} مكرر، تخطي...")
                continue
            
            print(f"📌 معالجة المنشور رقم: {sig}")
            
            # تنظيف النص من أكواد الـ HTML
            raw_text = raw_html_text.replace('<br/>', '\n').replace('<br>', '\n')
            raw_text = re.sub(r'<[^>]+>', '', raw_text).strip()
            
            clean_text = clean_news_text(raw_text)
            
            if post_to_facebook(clean_text):
                print(f"✅ تم نشر المنشور {sig} بنجاح!")
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(sig + "\n")
                history.append(sig)
                time.sleep(5)
            else:
                print(f"❌ فشل نشر المنشور {sig}")
            
    except Exception as e:
        print(f"⚠️ خطأ عام: {e}")

if __name__ == "__main__":
    main()
