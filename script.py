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

DB_FILE = "last_news_id.txt"
FIXED_HASHTAG = "#قلعة_الاخبار_العراقية"

SOURCES = ['Iraq_weather12', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'independetiraqia', 'alarabiya_brk', 'SkyNewsArabia_Breaking']

# القائمة السوداء المعدلة (تنظيف قسري لأسماء القنوات)
BLACKLIST = [
    'سكاي نيوز', 'العربية عاجل', 'اندبندنت_عراقية', 'اندبندنت عربية', 
    'طقس العراق', 'قناة', 'اشترك', 'المصدر', 'تليكرام', 'تيليجرام',
    'الجزيرة', 'بلومبرغ', 'العربية', 'سكاي', 'Sky News', 'Al Arabiya', 'Independent'
]

def clean_news_text(text):
    """تنظيف ذكي: يحذف أسماء القنوات والروابط ويبقي الهاشتاقات العامة"""
    # 1. حذف الروابط ومعرفات التليجرام
    text = re.sub(r'http\S+|t\.me\/\S+|@\S+', '', text)
    
    # 2. حذف أسماء المصادر من القائمة السوداء (سواء كانت نص أو هاشتاق)
    for word in BLACKLIST:
        text = re.sub(rf'#?{word}\w*', '', text, flags=re.IGNORECASE)
    
    # 3. تنظيف الشوائب عبر جيميناي (بدون تغيير الصياغة)
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
    """نشر للفيسبوك مع كاشف أخطاء تفصيلي"""
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
        r = requests.post(url, data=payload, timeout=10)
        result = r.json()
        if r.status_code == 200:
            print("✅ Facebook: تم النشر بنجاح")
        else:
            print(f"❌ Facebook Error {r.status_code}: {result.get('error', {}).get('message', 'Unknown Error')}")
    except Exception as e:
        print(f"⚠️ FB Connection Error: {e}")

def post_to_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': MY_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        requests.post(url, data=payload, timeout=10)
        print("✅ Telegram: تم النشر بنجاح")
    except:
        print("❌ Telegram: فشل النشر")

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
                header = "🚨 <b>عاجل</b>" if is_urgent else "📌 <b>خبر</b>"
                
                tg_msg = f"{header}\n\n<blockquote>{clean_text}</blockquote>\n\n✅ <b>للمتابعة اضغط اشتراك:</b>\n{MY_CHANNEL_LINK}\n\n{FIXED_HASHTAG}"
                fb_msg = f"{header.replace('<b>','').replace('</b>','')}\n\n{clean_text}\n\n{FIXED_HASHTAG}"
                
                post_to_telegram(tg_msg)
                post_to_facebook(fb_msg)
                
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(sig + "\n")
                history.append(sig)
                time.sleep(10)
                break 
        except:
            continue

if __name__ == "__main__":
    main()
