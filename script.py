import os
import re
import requests
import time
import tweepy
from datetime import datetime

# --- الإعدادات ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GMY_API_KEY = os.getenv('GMY')
MY_CHANNEL = os.getenv('NEWS_CHANNEL')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')
MY_CHANNEL_LINK = os.getenv('MY_CHANNEL_LINK')

# إعدادات ثريدز وتويتر الجديدة
THREADS_ACCESS_TOKEN = os.getenv('THREADS_ACCESS_TOKEN')
THREADS_USER_ID = os.getenv('THREADS_USER_ID')
TW_API_KEY = os.getenv('TWITTER_API_KEY')
TW_API_SECRET = os.getenv('TWITTER_API_SECRET')
TW_ACC_TOKEN = os.getenv('TWITTER_ACCESS_TOKEN')
TW_ACC_SECRET = os.getenv('TWITTER_ACCESS_SECRET')

DB_FILE = "last_news_id.txt"
FIXED_HASHTAG = "#قلعة_الاخبار_العراقية"
SOURCES = ['Iraq_weather12', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'independetiraqia', 'alarabiya_brk', 'SkyNewsArabia_Breaking']

def post_to_twitter(message):
    if not TW_API_KEY: return
    try:
        client = tweepy.Client(consumer_key=TW_API_KEY, consumer_secret=TW_API_SECRET,
                               access_token=TW_ACC_TOKEN, access_token_secret=TW_ACC_SECRET)
        client.create_tweet(text=message)
        print("✅ Twitter: تم النشر بنجاح")
    except Exception as e: print(f"❌ Twitter Error: {e}")

def post_to_threads(message):
    if not THREADS_ACCESS_TOKEN: return
    try:
        url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
        res = requests.post(url, data={'access_token': THREADS_ACCESS_TOKEN, 'text': message, 'media_type': 'TEXT'}).json()
        container_id = res.get('id')
        if container_id:
            time.sleep(2)
            requests.post(f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish", 
                          data={'creation_id': container_id, 'access_token': THREADS_ACCESS_TOKEN})
            print("✅ Threads: تم النشر بنجاح")
        else: print(f"❌ Threads Error: {res.get('error', {}).get('message')}")
    except Exception as e: print(f"⚠️ Threads Connection: {e}")

def post_to_facebook(message):
    try:
        r = requests.post(f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed", 
                          data={'message': message, 'access_token': FB_PAGE_TOKEN})
        if r.status_code == 200: print("✅ Facebook: تم النشر بنجاح")
        else: print(f"❌ Facebook Error: {r.json().get('error', {}).get('message')}")
    except Exception as e: print(f"⚠️ FB Error: {e}")

def post_to_telegram(text):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                      data={'chat_id': MY_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True})
        print("✅ Telegram: تم النشر بنجاح")
    except: print("❌ Telegram: فشل النشر")

def clean_news_text(text):
    text = re.sub(r'http\S+|t\.me\/\S+|@\S+', '', text)
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GMY_API_KEY}"
        prompt = f"قم بحذف الروابط وأي توقيع لقنوات إخبارية من النص التالي فقط. حافظ على النص الأصلي:\n\n{text}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, json=payload, timeout=10).json()
        if 'candidates' in res:
            text = res['candidates'][0]['content']['parts'][0]['text'].strip()
    except: pass
    return re.sub(r'\s+', ' ', text).strip()

def is_work_time():
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def main():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    if not is_work_time(): return

    with open(DB_FILE, 'r', encoding='utf-8') as f: history = f.read().splitlines()

    for src in SOURCES:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*>(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
            for item in reversed(items[-5:]):
                if 'tgme_widget_message_photo' in item or 'tgme_widget_message_video' in item: continue
                msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
                if not msg_match: continue
                raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip()
                if len(raw_text) < 25: continue
                sig = raw_text[:80]
                if sig in history: continue
                
                clean_text = clean_news_text(raw_text)
                is_urgent = any(word in raw_text for word in ["عاجل", "الآن"])
                header = "🚨 عاجل" if is_urgent else "📌 خبر"
                
                tg_msg = f"<b>{header}</b>\n\n<blockquote>{clean_text}</blockquote>\n\n✅ <b>للمتابعة:</b>\n{MY_CHANNEL_LINK}\n\n{FIXED_HASHTAG}"
                universal_msg = f"{header}\n\n{clean_text}\n\n{FIXED_HASHTAG}"
                
                post_to_telegram(tg_msg)
                post_to_facebook(universal_msg)
                post_to_threads(universal_msg)
                post_to_twitter(universal_msg)
                
                with open(DB_FILE, 'a', encoding='utf-8') as f: f.write(sig + "\n")
                history.append(sig)
                time.sleep(10)
                break 
        except: continue

if __name__ == "__main__":
    main()
