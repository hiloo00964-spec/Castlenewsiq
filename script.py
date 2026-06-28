import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات الأساسية لبوت الأخبار العراقي ---
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')

DB_FILE = "last_news_id.txt"
SOURCE_CHANNEL = 'Castlenewsiq'  # مراقبة قناة الأخبار حصراً

def is_work_time():
    """فحص وقت العمل بتوقيت العراق (UTC+3) من 9 صباحاً إلى 11 مساءً"""
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def clean_news_text(text):
    """تنظيف محلي خالص: يحذف فقط توقيع قناة الأخبار المحدد دون مساس بأي محتوى آخر"""
    if not text:
        return ""
    
    # حذف عبارة الاشتراك ورابط قناة الأخبار المحددة بالكامل
    pattern = r'للمزيد\s*من\s*الأخبار\s*اشترك\s*في\s*قناتنا:\s*👇\s*\n?https://t\.me/Castlenewsiq'
    text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # تنظيف الأسطر الفارغة المتكررة الناتجة عن الحذف
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
            print("✅ Facebook: تم النشر بنجاح وثبات")
            return True
        else:
            print(f"❌ Facebook Error: {r.text}")
            return False
    except Exception as e:
        print(f"⚠️ FB Connection Error: {e}")
        return False

def main():
    print("🚀 بدء تشغيل جولة فحص بوت الأخبار...")
    
    if not is_work_time():
        print("🌙 خارج وقت العمل المحدد (9 صباحاً - 11 مساءً بتوقيت العراق). تم إيقاف الدورة لحفظ الجهد.")
        return

    # ♻️ ميزة التصفير التلقائي: تفريغ ملف التاريخ كل أسبوع (7 أيام)
    if os.path.exists(DB_FILE):
        file_age_seconds = time.time() - os.path.getmtime(DB_FILE)
        if file_age_seconds >= 604800:
            print("♻️ مر أسبوع كامل على ملف التاريخ، جاري تنظيفه وتصفيره تلقائياً...")
            with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")

    if not os.path.exists(DB_FILE):
        print(f"📝 إنشاء ملف تاريخ جديد باسم: {DB_FILE}")
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()
    print(f"📂 تم تحميل الذاكرة بنجاح: تحتوي على [{len(history)}] معرّف خبر منشورة سابقاً.")

    try:
        url = f"https://t.me/s/{SOURCE_CHANNEL}"
        print(f"🌐 جاري سحب البيانات الحية من رابط التليجرام: {url}")
        res = requests.get(url, timeout=15)
        
        # التقاط المنشورات بشكل مرن ومقاوم للتغييرات الهيكلية
        items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*data-post="[^"\/]+/(\d+)"[^>]*>(.*?)(?=<div class="tgme_widget_message_wrap|$)', res.text, re.DOTALL)
        
        print(f"📊 إجمالي المنشورات المكتشفة في صفحة التليجرام حالياً: {len(items)}")
        
        if not items:
            print("⚠️ تنبيه: لم يتم العثور على أي منشورات داخل كود الصفحة! قد يكون الهيكل تغير أو المعرف خطأ.")
            return

        last_5 = items[-5:]
        print(f"🔍 جاري فحص آخر {len(last_5)} منشورات في القناة بالترتيب (من الأحدث للأقدم)...")

        for msg_id, item in reversed(last_5):
            sig = msg_id.strip()
            print(f"\n⚙️ --- فحص المنشور رقم [{sig}] ---")
            
            if 'tgme_widget_message_video' in item:
                print(f"⏭️ تخطي المنشور [{sig}]: لأن محتواه عبارة عن فيديو.")
                continue
            
            if sig in history:
                print(f"⏭️ تخطي المنشور [{sig}]: منشور سابقاً وموجود داخل ملف التاريخ (last_news_id.txt).")
                continue
            
            # 1. استخراج النص الأصلي للمنشور
            msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
            raw_text = ""
            if msg_match:
                raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip()
            
            # 2. استخراج رابط الصورة إن وجد
            photo_match = re.search(r'background-image:\s*url\(\s*[\'"]?(.*?)[\'"]?\s*\)', item)
            photo_url = photo_match.group(1) if photo_match else None
            
            if not raw_text and not photo_url:
                print(f"⏭️ تخطي المنشور [{sig}]: منشور فارغ تماماً لا يحتوي على نص أو صورة.")
                continue
            
            clean_text = clean_news_text(raw_text)
            print(f"📝 النص المستخرج بعد تنظيف التوقيع محلياً:\n{clean_text[:120]}...")
            
            local_photo_path = None
            if photo_url:
                try:
                    print(f"📸 جاري تحميل صورة المنشور مؤقتاً من السيرفر...")
                    img_res = requests.get(photo_url, timeout=12)
                    if img_res.status_code == 200:
                        local_photo_path = "temp_castle_img.jpg"
                        with open(local_photo_path, "wb") as img_f:
                            img_f.write(img_res.content)
                        print("✅ تم تحميل الصورة بنجاح وهي جاهزة للنشر.")
                except Exception as img_err:
                    print(f"⚠️ فشل في تحميل الصورة مؤقتاً: {img_err}")
            
            print(f"🚀 جاري إرسال ونقل الخبر رقم [{sig}] إلى الفيسبوك الآن...")
            success = post_to_facebook(clean_text, local_photo_path)
            
            if local_photo_path and os.path.exists(local_photo_path):
                os.remove(local_photo_path)
                print("🗑️ تم حذف الصورة المؤقتة بنجاح.")
            
            if success:
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(sig + "\n")
                history.append(sig)
                print(f"💾 تم قفل المنشور وحفظ المعرّف [{sig}] بملف التاريخ لمنع التكرار نهائياً.")
                
                time.sleep(10)
                break
        else:
            print("\n🏁 نتيجة الدورة: تم فحص الخمسة الأواخر بالكامل، وكلها مكررة وموجودة بالذاكرة مسبقاً.")
                
    except Exception as e:
        print(f"⚠️ خطأ عام أثناء تشغيل الدورة: {e}")

if __name__ == "__main__":
    main()
