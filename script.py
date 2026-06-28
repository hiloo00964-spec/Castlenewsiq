def main():
    if not is_work_time():
        print("🌙 خارج وقت العمل المحدد (9 صباحاً - 11 مساءً بتوقيت العراق). تم إيقاف الدورة لحفظ الجهد.")
        return

    # ♻️ ميزة التصفير التلقائي: تفريغ ملف التاريخ كل أسبوع (7 أيام = 604800 ثانية)
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
        
        # 🔥 التحديث الذهبي والمرن: سحب المنشورات بشكل مستقل عن وسوم الإغلاق المعقدة لضمان عدم الفشل
        items = re.findall(r'<div class="tgme_widget_message_wrap[^>]*data-post="[^"\/]+/(\d+)"[^>]*>(.*?)(?=<div class="tgme_widget_message_wrap|$)', res.text, re.DOTALL)
        
        if not items:
            print("⚠️ تنبيه: لم يتم العثور على أي منشورات داخل كود الصفحة، تأكد من معرف القناة أو هيكل الرابط.")
            return

        for msg_id, item in reversed(items[-5:]):
            if 'tgme_widget_message_video' in item:
                continue
            
            sig = msg_id.strip()
            
            if not sig or sig in history:
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
                continue
            
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
