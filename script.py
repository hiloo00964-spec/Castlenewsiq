\import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')
DB_FILE = "last_news_id.txt"
SOURCE_CHANNEL = 'Castlenewsiq'

def clean_news_text(text):
    if not text: return ""
    # حذف التوقيع المطلوب بدقة
    text = re.sub(r'للمزيد\s*من\s*الأخبار\s*اشترك\s*في\s*قناتنا:\s*👇\s*\n?https://t\.me/Castlenewsiq', '', text)
    return text.strip()

def post_to_facebook(message, image_url=None):
    try:
        if image_url:
            # تحميل الصورة مؤقتاً
            img_data = requests.get(image_url).content
            with open('temp_img.jpg', 'wb') as handler: handler.write(img_data)
            
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            files = {'source': open('temp_img.jpg', 'rb')}
            payload = {'caption': message, 'access_token': FB_PAGE_TOKEN}
            r = requests.post(url, data=payload, files=files, timeout=25)
        else:
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
            payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
            r = requests.post(url, data=payload, timeout=15)
            
        return r.status_code == 200
    except Exception as e:
        print(f"⚠️ خطأ في النشر: {e}")
        return False

def main():
    if not os.path.exists(DB_FILE): open(DB_FILE, 'w').close()
    with open(DB_FILE, 'r', encoding='utf-8') as f: history = f.read().splitlines()

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/120.0.0.0'}
    res = requests.get(f"https://t.me/s/{SOURCE_CHANNEL}", headers=headers, timeout=15)
    
    # البحث عن المنشورات
    items = re.findall(r'data-post="[^"\/]+/(\d+)"(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
    
    for msg_id, item in reversed(items[-5:]):
        if msg_id.strip() in history: continue
        
        # استخراج النص
        msg_match = re.search(r'class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
        raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip() if msg_match else ""
        clean_text = clean_news_text(raw_text)
        
        # استخراج الصورة (إذا وجدت)
        img_match = re.search(r'background-image:url\(\'([^\']+)\'\)', item)
        img_url = img_match.group(1) if img_match else None
        
        if post_to_facebook(clean_text, img_url):
            print(f"✅ تم نشر المنشور {msg_id}")
            with open(DB_FILE, 'a', encoding='utf-8') as f: f.write(msg_id + "\n")
            time.sleep(5)

if __name__ == "__main__":
    main()
