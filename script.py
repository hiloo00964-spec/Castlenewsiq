import os
import re
import requests
import time
import random
from datetime import datetime

# --- الإعدادات (تُسحب من الـ Secrets الخاصة بك) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GMY_API_KEY = os.getenv('GMY')
MY_CHANNEL = os.getenv('NEWS_CHANNEL')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')
MY_CHANNEL_LINK = os.getenv('MY_CHANNEL_LINK')

DB_FILE = "last_news_id.txt"
FIXED_HASHTAG = "#قلعة_الاخبار_العراقية"

# مصادر الأخبار
SOURCES = ['Iraq_weather12', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'independetiraqia', 'alarabiya_brk', 'SkyNewsArabia_Breaking']

def smart_clean_with_gemini(text):
    """استخدام جيميناي لتنظيف الخبر وجعله احترافياً"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GMY_API_KEY}"
        prompt = (
            "أنت محرر أخبار محترف. قم بتنظيف النص التالي: احذف روابط تليجرام (t.me)، "
            "احذف المعرفات التي تبدأ بـ @، احذف عبارات 'اشترك الآن' أو 'المصدر'. "
            "أبقِ محتوى الخبر كما هو وبصياغة قوية.\n\n"
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
    """توقيت العراق (GMT+3) من 9 صباحاً إلى 11 ليلاً"""
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def get_smart_hashtags(text):
    keywords = {"العراق": "#العراق", "بغداد": "#بغداد", "رواتب": "#الرواتب", "الدولار": "#الدولار", "طقس": "#الطقس"}
    found = [tag for key, tag in keywords.items() if key in text]
    if "عاجل" in text: found.insert(0, "#عاجل")
    found.append(FIXED_HASHTAG)
    return " ".join(list(dict.fromkeys(found)))

def post_to_facebook(message):
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
        requests.post(url, data=payload, timeout=10)
    except: pass

def post_to_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': MY_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        requests.post(url, data=payload, timeout=10)
    except: pass

def main():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    
    if not is_work_time():
        print("🌙 خارج وقت العمل (9ص - 11م)")
        return

    with open(DB_FILE, 'r', encoding='utf-8') as f: history = f.read().splitlines()

    for src in SOURCES:
        try:
            print(f"🔍 فحص: {src}")
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            # استخراج الرسائل مع نظام الفلترة القديم (تجاهل الميديا)
            items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*>(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
            
            for item in reversed(items[-5:]):
                if any(x in item for x in ['tgme_widget_message_photo', 'tgme_widget_message_video']):
                    continue # تجاهل أي رسالة فيها صورة أو فيديو
                
                msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
                if not msg_match: continue
                
                raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip()
                if len(raw_text) < 20: continue
                
                sig = raw_text[:100]
                if sig in history: continue
                
                # التنظيف بجيميناي
                clean_text = smart_clean_with_gemini(raw_text)
                hashtags = get_smart_hashtags(clean_text)
                
                is_urgent = any(word in raw_text for word in ["عاجل", "الآن"])
                header = "🚨 <b>عاجل</b>" if is_urgent else "📌 <b>خبر</b>"
                
                # إعداد النصوص
                tg_msg = f"{header}\n\n<blockquote>{clean_text}</blockquote>\n\n✅ <b>للمتابعة اضغط اشتراك:</b>\n{MY_CHANNEL_LINK}\n\n{hashtags}"
                fb_msg = f"{header.replace('<b>','').replace('</b>','')}\n\n{clean_text}\n\n{hashtags}"
                
                post_to_telegram(tg_msg)
                post_to_facebook(fb_msg)
                
                with open(DB_FILE, 'a', encoding='utf-8') as f: f.write(sig + "\n")
                history.append(sig)
                time.sleep(random.randint(10, 20))
                break 
        except: continue

if __name__ == "__main__":
    main()
