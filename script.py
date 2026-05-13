import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GMY_API_KEY = os.getenv('GMY')
MY_CHANNEL = os.getenv('NEWS_CHANNEL')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')
MY_CHANNEL_LINK = os.getenv('MY_CHANNEL_LINK')
# إعدادات ثريدز الجديدة
THREADS_ACCESS_TOKEN = os.getenv('THREADS_ACCESS_TOKEN')
THREADS_USER_ID = os.getenv('THREADS_USER_ID')

DB_FILE = "last_news_id.txt"
FIXED_HASHTAG = "#قلعة_الاخبار_العراقية"

SOURCES = ['Iraq_weather12', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'independetiraqia', 'alarabiya_brk', 'SkyNewsArabia_Breaking']

BLACKLIST = [
    'سكاي نيوز', 'العربية عاجل', 'اندبندنت_عراقية', 'اندبندنت عربية', 
    'طقس العراق', 'قناة', 'اشترك', 'المصدر', 'تليكرام', 'تيليجرام',
    'الجزيرة', 'بلومبرغ', 'العربية', 'سكاي', 'Sky News', 'Al Arabiya', 'Independent'
]

def clean_news_text(text):
    text = re.sub(r'http\S+|t\.me\/\S+|@\S+', '', text)
    for word in BLACKLIST:
        text = re.sub(rf'#?{word}\w*', '', text, flags=re.IGNORECASE)
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GMY_API_KEY}"
        prompt = f"قم بحذف الروابط وأي توقيع لقنوات إخبارية من النص التالي فقط. ممنوع تغيير صياغة الخبر أو حذف الهاشتاقات العامة مثل #العراق، حافظ على النص الأصلي:\n\n{text}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if 'candidates' in data:
            text = data['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        pass
    return re.sub(r'\s+', ' ', text).strip()

def is_work_time():
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def post_to_facebook(message):
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
        r = requests.post(url, data=payload, timeout=10)
        result = r.json()
        if r.status_code == 200:
            print("✅ Facebook: تم النشر بنجاح")
        else:
            print(f"❌ Facebook Error: {result.get('error', {}).get('message', 'Unknown Error')}")
    except Exception as e:
        print(f"⚠️ FB Connection Error: {e}")

def post_to_threads(message):
    """نشر لثريدز مع نظام كشف أخطاء متقدم"""
    if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
        print("⚠️ Threads: تم تخطي النشر (السيكرتس غير مضافة)")
        return

    try:
        # 1. إنشاء الحاوية (Container)
        url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
        payload = {
            'access_token': THREADS_ACCESS_TOKEN,
            'text': message,
            'media_type': 'TEXT'
        }
        r = requests.post(url, data=payload, timeout=15)
        res = r.json()
        container_id = res.get('id')

        if container_id:
            # 2. النشر الفعلي (Publish)
            publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
            publish_payload = {
                'creation_id': container_id,
                'access_token': THREADS_ACCESS_TOKEN
            }
            # انتظار ثانية واحدة لضمان معالجة الحاوية
            time.sleep(2)
            rp = requests.post(publish_url, data=publish_payload, timeout=15)
            if rp.status_code == 200:
                print("✅ Threads: تم النشر بنجاح")
            else:
                print(f"❌ Threads Publish Error: {rp.json().get('error', {}).get('message')}")
        else:
            print(f"❌ Threads Container Error: {res.get('error', {}).get('message', 'Unknown Error')}")
    except Exception as e:
        print(f"⚠️ Threads Connection Error: {e}")

def post_to_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': MY_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Telegram: تم النشر بنجاح")
        else:
            print(f"❌ Telegram Error: {r.text}")
    except:
        print("❌ Telegram: فشل الاتصال")

def main():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    if not is_work_time():
        print("🌙 خارج وقت العمل (9ص - 11م)")
        return

    with open(DB_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    for src in SOURCES:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*>(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
            
            for item in reversed(items[-5:]):
                if 'tgme_widget_message_photo' in item or 'tgme_widget_message_video' in item:
                    continue
                
                msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
                if not msg_match: continue
                
                raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip()
                if len(raw_text) < 25: continue
                
                sig = raw_text[:80]
                if sig in history: continue
                
                clean_text = clean_news_text(raw_text)
                is_urgent = any(word in raw_text for word in ["عاجل", "الآن"])
                header = "🚨 عاجل" if is_urgent else "📌 خبر"
                
                # الرسائل
                tg_msg = f"<b>{header}</b>\n\n<blockquote>{clean_text}</blockquote>\n\n✅ <b>للمتابعة اضغط اشتراك:</b>\n{MY_CHANNEL_LINK}\n\n{FIXED_HASHTAG}"
                universal_msg = f"{header}\n\n{clean_text}\n\n{FIXED_HASHTAG}"
                
                # النشر في كل المنصات
                post_to_telegram(tg_msg)
                post_to_facebook(universal_msg)
                post_to_threads(universal_msg)
                
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(sig + "\n")
                history.append(sig)
                time.sleep(10)
                break 
        except Exception as e:
            print(f"Error in source {src}: {e}")
            continue

if __name__ == "__main__":
    main()
