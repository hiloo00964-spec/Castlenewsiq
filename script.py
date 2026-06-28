import os
import re
import requests
import time
from datetime import datetime

# --- الإعدادات ---
GMY_API_KEY = os.getenv('GMY')
FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_PAGE_TOKEN = os.getenv('FB_TOKEN')

DB_FILE = "last_news_id.txt"
FIXED_HASHTAG = "#قلعة_الاخبار_العراقية"

SOURCES = ['inainaiq', 'IRAQ2TV', 'iraqq90', 'iraqi1_news', 'Iraq_now3', 'ikeeralahda']

# القائمة السوداء المحدثة لفلترة الكلمات غير المرغوبة
BLACKLIST = [
    'سكاي نيوز', 'العربية عاجل', 'اندبندنت_عراقية', 'اندبندنت عربية', 
    'طقس العراق', 'إندبندنت_عراقية', 'قناة','&rlm;', 'اشترك', '#اندبندنت_عراقية', 'pinned', 'المصدر', 'اطلب دريسك الآن بأعلى جودة\n', 
    'تليكرام', 'تيليجرام', 'الجزيرة',' i24NEWS ', 'بلومبرغ', 'العربية', 'سكاي', 
    'Sky News', 'Al Arabiya', 'Independent', 'شبكة اخبار العراق',
    '&quot;', '&rlm;', '"' 
]

def clean_news_text(text):
    """تنظيف ذكي: يحذف المصادر والهاشتاقات الخاصة بالمنافسين عبر جيميناي مع الحفاظ على بنية النص"""
    # تنظيف معرفات وقنوات التليجرام فقط، وترك الروابط الخارجية لكي لا تتعطل
    text = re.sub(r't\.me\/\S+|@\S+', '', text)
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GMY_API_KEY}"
        
        prompt = (
            "أنت محرر أخبار محترف. قم بمعالجة النص التالي:\n"
            "1. احذف أي هاشتاق يشير لاسم المصدر (مثل #إندبندنت_عراقية، #العربية، #سكاي_نيوز).\n"
            "2. احذف أي جملة في نهاية الخبر تشير للمصدر الأصلي بشكل صريح.\n"
            "3. حافظ على محتوى الخبر الأصلي كاملاً دون تغيير صياغته الأصلية.\n"
            "4. حافظ على الهاشتاقات العامة فقط مثل #العراق أو #بغداد.\n\n"
            f"النص:\n{text}"
        )
        
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        res = requests.post(url, json=payload, timeout=15)
        data = res.json()
        if 'candidates' in data:
            text = data['candidates'][0]['content']['parts'][0]['text'].strip()
    except:
        # في حال فشل Gemini، نستخدم التنظيف اليدوي من القائمة السوداء
        for word in BLACKLIST:
            text = re.sub(rf'#?{word}\w*', '', text, flags=re.IGNORECASE)
    
    return re.sub(r'\s+', ' ', text).strip()

def is_work_time():
    # توقيت العراق (UTC+3)
    current_hour = (datetime.utcnow().hour + 3) % 24
    return 9 <= current_hour <= 23

def post_to_facebook(message):
    """ينشر المنشور الرئيسي ويعيد معرف المنشور (Post ID) لزرع التعليق"""
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
        payload = {'message': message, 'access_token': FB_PAGE_TOKEN}
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            res_data = r.json()
            print("✅ Facebook: تم نشر المنشور الرئيسي بنجاح")
            return res_data.get('id')
        else:
            print(f"❌ Facebook Error: {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ FB Connection Error: {e}")
        return None

def post_comment_to_facebook(post_id, comment_text):
    """ينشر التعليق الأول المحتوي على الروابط باسم الصفحة"""
    try:
        url = f"https://graph.facebook.com/v19.0/{post_id}/comments"
        payload = {'message': comment_text, 'access_token': FB_PAGE_TOKEN}
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Facebook: تم إضافة الروابط في التعليق الأول بنجاح.")
        else:
            print(f"❌ Facebook Comment Error: {r.text}")
    except Exception as e:
        print(f"⚠️ FB Comment Error: {e}")

def main():
    # نظام التصفير التلقائي: فحص عمر ملف التاريخ وتصفيره كل يومين (48 ساعة) لضمان خفة وسرعة المستودع
    if os.path.exists(DB_FILE):
        file_age_seconds = time.time() - os.path.getmtime(DB_FILE)
        if file_age_seconds > 2 * 24 * 3600:
            print("♻️ مر 48 ساعة على ملف التاريخ.. يتم التصفير التلقائي الآن للمحافظة على سرعة البوت.")
            with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    else:
        with open(DB_FILE, 'w', encoding='utf-8') as f: f.write("INIT\n")
    
    if not is_work_time():
        print("🌙 خارج وقت العمل (9ص - 11م)")
        return

    with open(DB_FILE, 'r', encoding='utf-8') as f:
        history = f.read().splitlines()

    for src in SOURCES:
        try:
            res = requests.get(f"https://t.me/s/{src}", timeout=15)
            # تحديث تجميع المنشورات لالتقاط الوسم الكامل بما يحتويه من data-post قاطع للتكرار
            items = re.findall(r'(<div class="tgme_widget_message_wrap[^>]*>.*?</div>\s*</div>\s*</div>)', res.text, re.DOTALL)
            
            for item in reversed(items[-5:]):
                # تخطي المنشورات التي تحتوي صور أو فيديو
                if 'tgme_widget_message_photo' in item or 'tgme_widget_message_video' in item:
                    continue
                
                # استخراج الـ Telegram Message ID الفريد من خاصية data-post
                post_id_match = re.search(r'data-post="([^"]+)"', item)
                if not post_id_match: continue
                post_unique_id = post_id_match.group(1) # النتيجة تكون مثل: iraqi1_news/12345
                
                # فحص منع التكرار المضمون 100%
                if post_unique_id in history: continue
                
                msg_match = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', item, re.DOTALL)
                if not msg_match: continue
                
                raw_text = re.sub(r'<[^>]+>', '', msg_match.group(1).replace('<br/>', '\n').replace('<br>', '\n')).strip()
                if len(raw_text) < 25: continue
                
                # --- استراتيجية فصل الروابط الخارجية للتعليق الأول ---
                url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'
                all_links = re.findall(url_pattern, raw_text)
                
                # عزل الروابط الخارجية الحقيقية (واستبعاد روابط تليجرام لكي لا تنشر بالتعليقات كسبام)
                external_links = [link for link in all_links if "t.me" not in link]
                
                # إزالة الروابط الخارجية مؤقتاً من النص لتنظيف المحتوى الإخباري بدقة عبر جيميناي
                main_text_for_cleaning = raw_text
                for link in external_links:
                    main_text_for_cleaning = main_text_for_cleaning.replace(link, "")
                
                # عملية التنظيف الذكي للنص الرئيسي
                clean_text = clean_news_text(main_text_for_cleaning)
                
                is_urgent = any(word in raw_text for word in ["عاجل", "الآن"])
                header = "🚨 عاجل" if is_urgent else "📌 خبر"
                
                # صياغة المنشور وحقن أسطر "عرض المزيد" في حال وجود روابط بحوزتنا
                if external_links:
                    # نقاط تفصلها أسطر فارغة لكسر الشاشة في تطبيق الموبايل وإظهار زر "عرض المزيد"
                    padding = "\n.\n.\n.\n.\n.\n.\n"
                    fb_msg = f"{header}\n\n{clean_text}\n\n{FIXED_HASHTAG}{padding}👇 لمتابعة التفاصيل وقراءة المصدر/الروابط، يرجى مراجعة التعليق الأول أسفل المنشور 👇"
                    comment_msg = "🔗 روابط المصادر والتفاصيل الرسمية الخاصة بالخبر:\n\n" + "\n".join(external_links)
                else:
                    fb_msg = f"{header}\n\n{clean_text}\n\n{FIXED_HASHTAG}"
                    comment_msg = None
                
                # 1. نشر المنشور الرئيسي واستلام الـ ID الخاص به
                fb_post_id = post_to_facebook(fb_msg)
                
                # 2. إذا نجح النشر وكانت هناك روابط، نزرع التعليق الأول فوراً
                if fb_post_id and comment_msg:
                    time.sleep(2) # تأخير بسيط لضمان استقرار السيرفر
                    post_comment_to_facebook(fb_post_id, comment_msg)
                
                # تسجيل المعرف الفريد في ملف التاريخ لمنع التكرار نهائياً
                with open(DB_FILE, 'a', encoding='utf-8') as f:
                    f.write(post_unique_id + "\n")
                history.append(post_unique_id)
                
                time.sleep(10)
                break 
        except Exception as e:
            print(f"⚠️ خطأ في المصدر {src}: {e}")
            continue

if __name__ == "__main__":
    main()
