import os
import re
import requests
import time
from google import genai

# --- الإعدادات من Secrets ---
BOT_TOKEN = os.getenv('BOT_TOKEN')
FB_TOKEN = os.getenv('FB_TOKEN')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
NEWS_CHANNEL = os.getenv('NEWS_CHANNEL')
JOBS_CHANNEL = os.getenv('JOBS_CHANNEL')
GEMINI_KEY = os.getenv('GMY')

# إعداد الذكاء الاصطناعي
client = genai.Client(api_key=GEMINI_KEY)

# المصادر
NEWS_SOURCES = ['Iraq_weather12', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'independetiraqia', 'alarabiya_brk', 'SkyNewsArabia_Breaking']
JOBS_SOURCES = ['JobsonIraq', 'iraq_jobs_1', 'vacancies_iraq', 'iraqijobs24']
NEWS_DB, JOBS_DB = "last_news_id.txt", "jobs_history.txt"
IMG_URGENT = "https://i.ibb.co/4ZdSnPKW/image.jpg"

def ai_process(text, mode="news"):
    try:
        if mode == "news":
            prompt = f"أعد صياغة هذا الخبر بأسلوب صحفي عراقي مقتضب جداً مع هاشتاقين ذكية (دولة وصنف): {text}"
        else:
            prompt = f"استخرج اسم المحافظة فقط كهاشتاق (مثلاً #بغداد) ونوع الوظيفة كهاشتاق: {text}"
        
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text.strip()
    except: return text

def post_tg(chat_id, text, img=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/"
        p = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        if img:
            p.update({'caption': text, 'photo': img})
            requests.post(url + "sendPhoto", data=p, timeout=20)
        else:
            requests.post(url + "sendMessage", data=p, timeout=20)
    except: pass

def post_fb(msg):
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        requests.post(url, data={'message': msg, 'access_token': FB_TOKEN}, timeout=20)
    except: pass

def clean(html):
    t = html.replace('</div>', ' ').replace('<br>', '\n').replace('<br/>', '\n')
    t = re.sub(r'#\w+|https?://\S+|t\.me/\S+', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def run_task(sources, db_file, channel, is_news=False):
    if not os.path.exists(db_file): open(db_file, 'w').close()
    with open(db_file, 'r', encoding='utf-8') as f: history = f.read().splitlines()
    
    for src in sources:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=20)
            items = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', res.text, re.DOTALL)
            for it in reversed(items[-10:]):
                raw = clean(it)
                if len(raw) < 30 or any(raw[:70] in h for h in history): continue
                
                processed = ai_process(raw, "news" if is_news else "jobs")
                
                if is_news:
                    urgent = any(x in it for x in ["عاجل", "الآن"])
                    header = "🚨 <b>عاجل</b>" if urgent else "📌 <b>خبر</b>"
                    post = f"{header}\n\n{processed}\n\n#قلعة_الاخبار_العراقية\n\nللمزيد من الأخبار اشترك بالقناة الآن :\nhttps://t.me/Castlenewsiq"
                    post_tg(channel, post, IMG_URGENT if urgent else None)
                    post_fb(post)
                else:
                    post = f"<b>💼 فرصة عمل جديدة</b>\n\n{raw}\n\n{processed}\n#قلعة_الوظائف_العراقية\n\nللمزيد من الوظائف اشترك بالقناة الآن :\nhttps://t.me/JobsonIraq"
                    post_tg(channel, post)
                
                with open(db_file, 'a', encoding='utf-8') as f: f.write(raw[:70] + "\n")
                time.sleep(5)
        except: continue

if __name__ == "__main__":
    # تشغيل الوظائف أولاً ثم الأخبار
    run_task(JOBS_SOURCES, JOBS_DB, JOBS_CHANNEL, is_news=False)
    run_task(NEWS_SOURCES, NEWS_DB, NEWS_CHANNEL, is_news=True)
