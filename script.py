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
            p = f"أعد صياغة هذا الخبر بأسلوب صحفي عراقي مقتضب جداً مع هاشتاقين ذكية: {text}"
        else:
            p = f"استخرج اسم المحافظة فقط كهاشتاق (مثلاً #بغداد) ونوع الوظيفة: {text}"
        res = model.generate_content(p)
        return res.text.strip() if res.text else text
    except: return text

def post_tg(chat_id, text, img=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        p = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if img:
            p.update({'caption': text, 'photo': img})
            requests.post(url + "sendPhoto", data=p, timeout=15)
        else:
            requests.post(url + "sendMessage", data=p, timeout=15)
    except: pass

def post_fb(msg):
    try:
        # إرسال للفيسبوك (للأخبار فقط)
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        requests.post(url, data={'message': msg, 'access_token': FB_TOKEN}, timeout=15)
    except: pass

def clean(html):
    t = html.replace('</div>', ' ').replace('<br>', '\n').replace('<br/>', '\n')
    t = re.sub(r'#\w+|https?://\S+|t\.me/\S+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

# --- دالة الأخبار (تليجرام + فيسبوك) ---
def run_news():
    print("بدء فحص الأخبار...")
    if not os.path.exists(NEWS_DB): open(NEWS_DB, 'w').close()
    with open(NEWS_DB, 'r', encoding='utf-8') as f: history = f.read().splitlines()
    
    for src in NEWS_SOURCES:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            items = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', res.text, re.DOTALL)
            for it in reversed(items[-5:]):
                raw = clean(it)
                if len(raw) < 25 or raw[:100] in history: continue
                
                ai_out = ai_process(raw, "news")
                urgent = any(x in it for x in ["عاجل", "الآن"])
                header = "🚨 <b>عاجل</b>" if urgent else "📌 <b>خبر</b>"
                post = f"{header}\n\n{ai_out}\n\n#قلعة_الاخبار_العراقية\n\nللمزيد: https://t.me/Castlenewsiq"
                
                post_tg(NEWS_CHANNEL, post, IMG_URGENT if urgent else None)
                post_fb(post) # النشر للفيس
                
                with open(NEWS_DB, 'a', encoding='utf-8') as f: f.write(raw[:100] + "\n")
                time.sleep(2)
        except: continue

# --- دالة الوظائف (تليجرام فقط) ---
def run_jobs():
    print("بدء فحص الوظائف...")
    if not os.path.exists(JOBS_DB): open(JOBS_DB, 'w').close()
    with open(JOBS_DB, 'r', encoding='utf-8') as f: history = f.read().splitlines()
    
    for src in JOBS_SOURCES:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            items = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', res.text, re.DOTALL)
            for it in reversed(items[-8:]):
                raw = clean(it)
                if len(raw) < 40 or raw[:100] in history: continue
                
                tags = ai_process(raw, "jobs")
                post = f"<b>💼 فرصة عمل جديدة</b>\n\n{raw}\n\n{tags}\n#قلعة_الوظائف_العراقية\n\nللمزيد: https://t.me/JobsonIraq"
                
                post_tg(JOBS_CHANNEL, post) # تليجرام فقط
                
                with open(JOBS_DB, 'a', encoding='utf-8') as f: f.write(raw[:100] + "\n")
                time.sleep(2)
        except: continue

if __name__ == "__main__":
    run_jobs() # نبدأ بالوظائف أولاً للتأكد من اشتغالها
    run_news() # ثم الأخبار
