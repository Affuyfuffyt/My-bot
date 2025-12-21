import os, subprocess, json, sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

# 1. تحميل الإعدادات من ملف Config
sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except ImportError:
    print("❌ خطأ: لم يتم العثور على ملف الإعدادات config.py")
    sys.exit(1)

# تعريف مراحل المحادثة
GET_NUM, GET_QUOTA = range(2)

# --- دالة البداية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 أهلاً بك! استخدم الأمر /add لإنشاء كود جديد.")

# --- الخطوة 1: طلب عدد الأجهزة ---
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("1️⃣ كم جهازاً تريد السماح به؟ (أرسل رقم فقط)")
    return GET_NUM

# --- الخطوة 2: استلام الرقم وطلب السعة ---
async def get_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['limit'] = update.message.text
    await update.message.reply_text("2️⃣ أدخل سعة البيانات (مثال: 1G أو 500M):")
    return GET_QUOTA

# --- الخطوة 3: إنشاء الكود النهائي ---
async def create_vless(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quota_input = update.message.text.upper()
    limit = context.user_data['limit']
    
    # تحويل السعة إلى Bytes
    try:
        num = int(''.join(filter(str.isdigit, quota_input)))
        if "G" in quota_input:
            bytes_limit = num * 1024 * 1024 * 1024
        else:
            bytes_limit = num * 1024 * 1024
    except:
        await update.message.reply_text("⚠️ خطأ في الصيغة، جرب كتابة 1G أو 500M.")
        return GET_QUOTA

    try:
        # توليد UUID وجلب IP
        uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
        ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        
        # تنسيق الإيميل للمراقب
        email = f"limit_{limit}_max_{bytes_limit}_{uuid[:4]}"
        
        # إضافة المستخدم لملف Xray
        config_path = "/usr/local/etc/xray/config.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": email})
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        # إعادة تشغيل Xray لتفعيل الإعدادات
        os.system("systemctl restart xray")
        
        # إنشاء الرابط
        link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{limit}_{quota_input}"
        
        await update.message.reply_text(f"✅ تم الإنشاء بنجاح!\n\n👥 عدد الأجهزة: {limit}\n💾 السعة: {quota_input}\n\n`{link}`")
    
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ تقني: {e}")
        
    return ConversationHandler.END

# دالة للإلغاء
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم إلغاء العملية.")
    return ConversationHandler.END

# --- تشغيل البوت ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", start_add)],
        states={
            GET_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_num)],
            GET_QUOTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_vless)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    print("✅ البوت يعمل الآن...")
    app.run_polling()
