import os
import re
import requests
import time
import random
import google.generativeai as genai

# --- الإعدادات من Secrets ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
FB_TOKEN = os.getenv('FB_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
NEWS_CHANNEL = os.getenv('NEWS_CHANNEL') # @Castlenewsiq
JOBS_CHANNEL = os.getenv('JOBS_CHANNEL') # @JobsonIraq
GEMINI_KEY = os.getenv('GMY')

# إعداد Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-pro')

# المصادر
NEWS_SOURCES = ['Iraq_weather12', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'independetiraqia', 'alarabiya_brk', 'SkyNewsArabia_Breaking']
JOBS_SOURCES = ['JobsonIraq', 'iraq_jobs_1', 'vacancies_iraq', 'iraqijobs24']
NEWS_DB, JOBS_DB = "last_news_id.txt", "jobs_history.txt"
IMG_URGENT = "https://i.ibb.co/4ZdSnPKW/image.jpg"

def ai_process(text, mode="news"):
    try:
        if mode == "news":
            prompt = f"أعد صياغة هذا الخبر بأسلوب صحفي عراقي واقترح له 2 هاشتاق ذكي (دولة، صنف): {text}"
        else:
            prompt = f"استخرج اسم المحافظة أو المكان من هذه الوظيفة وحوله لهاشتاق (مثلاً #وظائف_بغداد) وأضف هاشتاق للتخصص: {text}"
        
        response = model.generate_content(prompt)
        return response.text.strip() if response.text else text
    except: return text

def post_tg(chat_id, text, img=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML', 'disable_web_page_preview': False}
        if img:
            payload.update({'caption': text, 'photo': img})
            requests.post(url + "sendPhoto", data=payload, timeout=12)
        else:
            requests.post(url + "sendMessage", data=payload, timeout=12)
    except: pass

def post_fb(msg):
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        requests.post(url, data={'message': msg, 'access_token': FB_TOKEN}, timeout=12)
    except: pass

def clean(html):
    t = html.replace('</div>', ' ').replace('<br>', '\n').replace('<br/>', '\n')
    t = re.sub(r'#\w+|https?://\S+|t\.me/\S+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def run_news():
    if not os.path.exists(NEWS_DB): open(NEWS_DB, 'w').close()
    with open(NEWS_DB, 'r', encoding='utf-8') as f: history = f.read().splitlines()
    for src in NEWS_SOURCES:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            items = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', res.text, re.DOTALL)
            for it in reversed(items):
                raw = clean(it)
                if len(raw) < 25 or raw[:100] in history: continue
                
                ai_output = ai_process(raw, "news")
                is_urgent = any(x in it for x in ["عاجل", "الآن"])
                header = "🚨 <b>عاجل</b>" if is_urgent else "📌 <b>خبر</b>"
                
                # صياغة المنشور النهائي للأخبار
                final_post = f"{header}\n\n{ai_output}\n\n#قلعة_الاخبار_العراقية\n\nللمزيد من الأخبار اشترك بالقناة الآن :\nhttps://t.me/Castlenewsiq"
                
                post_tg(NEWS_CHANNEL, final_post, IMG_URGENT if is_urgent else None)
                post_fb(final_post)
                with open(NEWS_DB, 'a', encoding='utf-8') as f: f.write(raw[:100] + "\n")
                time.sleep(random.randint(30, 60))
        except: continue

def run_jobs():
    if not os.path.exists(JOBS_DB): open(JOBS_DB, 'w').close()
    with open(JOBS_DB, 'r', encoding='utf-8') as f: history = f.read().splitlines()
    for src in JOBS_SOURCES:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            items = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', res.text, re.DOTALL)
            for it in reversed(items):
                raw = clean(it)
                if len(raw) < 40 or raw[:100] in history: continue
                
                smart_hashtags = ai_process(raw, "jobs")
                
                # صياغة المنشور النهائي للوظائف (تليجرام فقط)
                final_post = f"<b>💼 فرصة عمل جديدة</b>\n\n{raw}\n\n{smart_hashtags}\n#قلعة_الوظائف_العراقية\n\nللمزيد من الوظائف اشترك بالقناة الآن :\nhttps://t.me/JobsonIraq"
                
                post_tg(JOBS_CHANNEL, final_post)
                with open(JOBS_DB, 'a', encoding='utf-8') as f: f.write(raw[:100] + "\n")
                time.sleep(random.randint(30, 60))
        except: continue

if __name__ == "__main__":
    run_news()
    run_jobs()
