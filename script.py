import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية للنسخة الثانية ---
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
    text = re.sub(r'للمزيد\s*من\s*الأخبار\s*اشترك\s*في\s*قناتنا:\s*👇\s*\n?https://t\.me/Castlenewsiq', '', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

def post_to_facebook(message, photo_path=None):
    try:
        if photo_path and os.path.exists(photo_path):
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            payload = {'caption': message, 'access_token': FB_PAGE_TOKEN}
            with open(photo_path, 'rb') as img_file:
                files = {'source': img_file}
                r = requests.post(url, data=payload, files=files, timeout=25)
        else:
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
            payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
            r = requests.post(url, data=payload, timeout=15)
            
        if r.status_code == 200:
            print("✅ Facebook: تم النشر بنجاح")
            return True
        else:
            print(f"❌ Facebook Error: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ FB Connection Error: {e}")
        return False

def main():
    print("🚀 بدء تنفيذ البوت...")
    if not is_work_time():
        print("🌙 خارج وقت العمل.")
        return

    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    try:
        # إضافة Headers للتمويه كمتصفح
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        print(f"🌐 الاتصال بقناة: {SOURCE_CHANNEL}")
        res = requests.get(f"https://t.me/s/{SOURCE_CHANNEL}", headers=headers, timeout=15)
        
        print(f"🔍 حالة الاستجابة: {res.status_code}")
        
        items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*data-post="[^"\/]+/(\d+)"[^>]*>(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
        
        print(f"📊 عدد المنشورات المكتشفة: {len(items)}")
        
        if not items:
            print("⚠️ تنبيه: لم يتم العثور على أي منشورات. تأكد من هيكل القناة.")
            return

        for msg_id, item in reversed(items[-5:]):
            sig = msg_id.strip()
            if sig in history:
                print(f"⏭️ تم تخطي المنشور {sig} لأنه موجود مسبقاً.")
                continue
            
            print(f"📌 معالجة المنشور رقم: {sig}")
            
            msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
            raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip() if msg_match else ""
            
            clean_text = clean_news_text(raw_text)
            
            # محاولة النشر
            success = post_to_facebook(clean_text)
            
            if success:
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(sig + "\n")
                print("💾 تم حفظ المعرف بنجاح.")
                break
                
    except Exception as e:
        print(f"⚠️ خطأ عام: {e}")

if __name__ == "__main__":
    main()
