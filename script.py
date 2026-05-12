import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات (تأكد من وجود هذه الأسماء في GitHub Secrets) ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
GMY_API_KEY = os.getenv('GMY')
MY_CHANNEL = os.getenv('NEWS_CHANNEL')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')
MY_CHANNEL_LINK = os.getenv('MY_CHANNEL_LINK')

DB_FILE = "last_news_id.txt"
FIXED_HASHTAG = "#قلعة_الاخبار_العراقية"

# المصادر المراد مراقبتها
SOURCES = ['Iraq_weather12', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'independetiraqia', 'alarabiya_brk', 'SkyNewsArabia_Breaking']

# القائمة السوداء (الأسماء التي تحذف فوراً أينما وجدت)
BLACKLIST = [
    'سكاي نيوز', 'العربية عاجل', 'اندبندنت_عراقية', 'اندبندنت عربية', 
    'طقس العراق', 'قناة', 'اشترك', 'المصدر', 'تليكرام', 'تيليجرام',
    'الجزيرة', 'بلومبرغ', 'العربية', 'سكاي', 'Sky News', 'Al Arabiya', 'Independent'
]

def clean_news_text(text):
    """تنظيف الخبر برمجياً من أسماء المصادر والروابط مع الحفاظ على الهاشتاقات العامة"""
    # 1. حذف الروابط (http) ومعرفات التليجرام (@)
    text = re.sub(r'http\S+|t\.me\/\S+|@\S+', '', text)
    
    # 2. حذف أسماء المصادر المحددة في الـ Blacklist (سواء كانت نص أو هاشتاق)
    for word in BLACKLIST:
        # يحذف الكلمة حتى لو مسبوقة بـ # أو متبوعة بكلمات أخرى (مثل #سكاي_نيوز_عربية)
        text = re.sub(rf'#?{word}\w*', '', text, flags=re.IGNORECASE)
    
    # 3. حذف أي رموز برمجية أو زخارف غير مرغوبة عبر جيميناي (بدون تغيير الصياغة)
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GMY_API_KEY}"
        prompt = f"قم بحذف الروابط وأي توقيع لقنوات إخبارية من النص التالي فقط. ممنوع تغيير صياغة الخبر، حافظ على النص كما هو:\n\n{text}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if 'candidates' in data:
            text = data['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        pass # إذا فشل جيميناي نعتمد على التنظيف البرمجي أعلاه
    
    # 4. تنظيف المسافات الزائدة المتبقية
    return re.sub(r'\s+', ' ', text).strip()

def is_work_time():
    """العمل من 9 صباحاً حتى 11 ليلاً بتوقيت العراق"""
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def post_to_facebook(message):
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
        r = requests.post(url, data=payload, timeout=10)
        print(f"FB Status: {r.status_code}")
    except Exception as e:
        print(f"FB Error: {e}")

def post_to_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': MY_CHANNEL, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"TG Error: {e}")

def main():
    # التأكد من وجود ملف الذاكرة
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
            # استخراج محتوى الرسائل
            items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*>(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
            
            for item in reversed(items[-5:]): # فحص آخر 5 رسائل من كل مصدر
                # تخطي الرسائل التي تحتوي على صور أو فيديوهات (بناءً على طلبك السابق للنصوص فقط)
                if 'tgme_widget_message_photo' in item or 'tgme_widget_message_video' in item:
                    continue
                
                msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
                if not msg_match: continue
                
                # تحويل HTML إلى نص عادي
                raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip()
                
                if len(raw_text) < 25: continue # تخطي النصوص القصيرة جداً
                
                # بصمة الخبر لمنع التكرار
                sig = raw_text[:80]
                if sig in history: continue
                
                # --- عملية التنظيف ---
                clean_text = clean_news_text(raw_text)
                
                # تحديد إذا كان الخبر عاجل
                is_urgent = any(word in raw_text for word in ["عاجل", "الآن"])
                header = "🚨 <b>عاجل</b>" if is_urgent else "📌 <b>خبر</b>"
                
                # تجهيز القالب النهائي
                tg_msg = f"{header}\n\n<blockquote>{clean_text}</blockquote>\n\n✅ <b>للمتابعة اضغط اشتراك:</b>\n{MY_CHANNEL_LINK}\n\n{FIXED_HASHTAG}"
                fb_msg = f"{header.replace('<b>','').replace('</b>','')}\n\n{clean_text}\n\n{FIXED_HASHTAG}"
                
                # النشر
                post_to_telegram(tg_msg)
                post_to_facebook(fb_msg)
                
                # حفظ في الذاكرة
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(sig + "\n")
                history.append(sig)
                
                print(f"✅ تم نشر خبر من مصدر: {src}")
                time.sleep(15) # فاصل زمني لتجنب الحظر
                break 
        except Exception as e:
            print(f"Error with source {src}: {e}")
            continue

if __name__ == "__main__":
    main()
