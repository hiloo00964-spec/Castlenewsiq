import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية لبوت الأخبار العراقي ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')

DB_FILE = "last_news_id.txt"
SOURCE_CHANNEL = 'Castlenewsiq'  # مراقبة قناة الأخبار حصراً بناءً على طلبك

def is_work_time():
    """فحص وقت العمل بتوقيت العراق (UTC+3) من 9 صباحاً إلى 11 مساءً"""
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def clean_news_text(text):
    """تنظيف محلي خالص: يحذف فقط توقيع قناة الأخبار المحدد دون مساس بأي محتوى آخر"""
    if not text:
        return ""
    
    # حذف عبارة الاشتراك ورابط قناة الأخبار المحددة بالكامل وبشكل مرن مع الأسطر
    pattern = r'للمزيد\s*من\s*الأخبار\s*اشترك\s*في\s*قناتنا:\s*👇\s*\n?https://t\.me/Castlenewsiq'
    text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # تنظيف الأسطر الفارغة المتكررة الناتجة عن الحذف ليكون المظهر متناسقاً
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    
    return text.strip()

def post_to_facebook(message, photo_path=None):
    """نشر النصوص والصور بالطريقة الآمنة والمجربة (تحميل، رفع كملف، تدمير ذاتي)"""
    try:
        if photo_path and os.path.exists(photo_path):
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            payload = {'caption': message, 'access_token': FB_PAGE_TOKEN}
            with open(photo_path, 'rb') as img_file:
                files = {'source': img_file}
                r = requests.post(url, data=payload, files=files, timeout=25)
        else:
            url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
            payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
            r = requests.post(url, data=payload, timeout=15)
            
        if r.status_code == 200:
            print("✅ Facebook: تم النشر بنجاح")
            return True
        else:
            print(f"❌ Facebook Error: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ FB Connection Error: {e}")
        return False

def main():
    if not is_work_time():
        print("🌙 خارج وقت العمل المحدد (9 صباحاً - 11 مساءً بتوقيت العراق). تم إيقاف الدورة لحفظ الجهد.")
        return

    # ♻️ ميزة التصفير التلقائي: تفريغ ملف التاريخ كل أسبوع (7 أيام = 604800 ثانية) للحفاظ على خفة المستودع
    if os.path.exists(DB_FILE):
        file_age_seconds = time.time() - os.path.getmtime(DB_FILE)
        if file_age_seconds >= 604800:
            print("♻️ مر أسبوع كامل على ملف التاريخ، جاري تنظيفه وتصفيره تلقائياً...")
            with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")

    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    try:
        res = requests.get(f"https://t.me/s/{SOURCE_CHANNEL}", timeout=15)
        
        # 🌟 الاعتماد الكلي على معرّف الـ ID الرقمي الفريد القادم من التليجرام لقفل التكرار قطعياً
        items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*data-post="[^"\/]+/(\d+)"[^>]*>(.*?)</div>\s*</div>\s*</div>', res.text, re.DOTALL)
        
        for msg_id, item in reversed(items[-5:]):
            if 'tgme_widget_message_video' in item:
                continue
            
            sig = msg_id.strip()
            
            if not sig or sig in history:
                continue
            
            # 1. استخراج النص الأصلي للمنشور كما هو
            msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
            raw_text = ""
            if msg_match:
                raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip()
            
            # 2. استخراج رابط الصورة ودعمها بالكامل داخل المنشور الإخباري
            photo_match = re.search(r'background-image:\s*url\(\s*[\'"]?(.*?)[\'"]?\s*\)', item)
            photo_url = photo_match.group(1) if photo_match else None
            
            if not raw_text and not photo_url:
                continue
            
            # معالجة النص وتنظيف التوقيع محلياً
            clean_text = clean_news_text(raw_text)
            
            local_photo_path = None
            if photo_url:
                try:
                    img_res = requests.get(photo_url, timeout=12)
                    if img_res.status_code == 200:
                        local_photo_path = "temp_castle_img.jpg"
                        with open(local_photo_path, "wb") as img_f:
                            img_f.write(img_res.content)
                        print("📸 تم سحب الصورة الإخبارية مؤقتاً وجاهزة للرفع...")
                except Exception as img_err:
                    print(f"⚠️ فشل في تحميل الصورة مؤقتاً: {img_err}")
            
            print(f"🚀 جاري نقل منشور الأخبار رقم [{sig}] من @{SOURCE_CHANNEL} إلى الفيسبوك...")
            success = post_to_facebook(clean_text, local_photo_path)
            
            # التدمير الذاتي للملفات المؤقتة لمنع تراكم الميديا في خوادم جيتهب
            if local_photo_path and os.path.exists(local_photo_path):
                os.remove(local_photo_path)
                print("🗑️ تم حذف الصورة المؤقتة بنجاح")
            
            if success:
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(sig + "\n")
                history.append(sig)
                
                time.sleep(10)
                break
                
    except Exception as e:
        print(f"⚠️ خطأ عام أثناء تشغيل الدورة: {e}")

if __name__ == "__main__":
    main()
