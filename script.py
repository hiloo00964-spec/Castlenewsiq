import os
import re
import requests
import time
import random
from datetime import datetime, timedelta

# --- الإعدادات (تُسحب من الـ Secrets الخاصة بك) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GMY_API_KEY = os.getenv('GMY')
MY_CHANNEL = os.getenv('NEWS_CHANNEL') # القناة من السكرت
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')

DB_FILE = "last_news_id.txt"
FIXED_HASHTAG = "#قلعة_الاخبار_العراقية"

SOURCES = ['Iraq_weather12', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'independetiraqia', 'alarabiya_brk', 'SkyNewsArabia_Breaking']

def smart_clean_with_gemini(text):
    """استخدام جيميناي لتنظيف الخبر وجعله احترافياً"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GMY_API_KEY}"
        prompt = (
            "أنت محرر أخبار محترف. قم بإعادة صياغة النص التالي مع حذف أي روابط قنوات تليجرام أو دعوات للاشتراك. "
            "حافظ على محتوى الخبر كاملاً ولا تلخصه بشكل يضيع التفاصيل.\n\n"
            f"النص:\n{text}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, json=payload, timeout=15)
        data = res.json()
        if 'candidates' in data:
            return data['candidates'][0]['content']['parts'][0]['text'].strip()
        return text
    except:
        return text

def is_work_time():
    """توقيت العراق (GMT+3)"""
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 8 <= current_hour < 24 # جعلناه يبدأ من 8 صباحاً

def manage_db_file():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT_SESSION\n")

def get_smart_hashtags(text):
    keywords = {"العراق": "#العراق", "بغداد": "#بغداد", "رواتب": "#الرواتب", "طقس": "#الطقس"}
    found = [tag for key, tag in keywords.items() if key in text]
    if "عاجل" in text: found.insert(0, "#عاجل")
    found.append(FIXED_HASHTAG)
    return " ".join(list(dict.fromkeys(found)))

def post_to_facebook(message):
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
        requests.post(url, data=payload)
    except: pass

def post_to_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': MY_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        requests.post(url, data=payload)
    except: pass

def main():
    manage_db_file()
    if not is_work_time(): return

    with open(DB_FILE, 'r', encoding='utf-8') as f: history = f.read().splitlines()

    for src in SOURCES:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            messages = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', res.text, re.DOTALL)
            
            for msg_html in reversed(messages[-5:]):
                raw_text = re.sub(r'<[^>]+>', '', msg_html.replace('<br/>', '\n').replace('<br>', '\n')).strip()
                if len(raw_text) < 20: continue
                
                sig = raw_text[:100]
                if sig in history: continue
                
                # التنظيف الذكي
                clean_text = smart_clean_with_gemini(raw_text)
                
                is_urgent = any(word in clean_text for word in ["عاجل", "الآن"])
                header = "🚨 <b>عاجل</b>" if is_urgent else "📌 <b>خبر</b>"
                hashtags = get_smart_hashtags(clean_text)
                
                # النشر
                telegram_text = f"{header}\n\n{clean_text}\n\n{hashtags}"
                post_to_telegram(telegram_text)
                post_to_facebook(f"{header.replace('<b>','').replace('</b>','')}\n\n{clean_text}\n\n{hashtags}")
                
                with open(DB_FILE, 'a', encoding='utf-8') as f: f.write(sig + "\n")
                history.append(sig)
                time.sleep(10)
                break 
        except: continue

if __name__ == "__main__":
    main()
