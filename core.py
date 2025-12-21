import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

# ربط ملف الإعدادات
sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except ImportError:
    print("خطأ: لم يتم العثور على ملف config.py")
    sys.exit(1)

# تعريف مرحلة "انتظار الرقم"
GET_NUM = 1

# --- دالة البداية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 أهلاً بك يا مدير! أرسل /add لإنشاء كود جديد.")

# --- دالة طلب الرقم (تبدأ عند /add) ---
async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("كم جهازاً تريد السماح به؟ (أرسل رقم فقط، 0 للحظر التام)")
    return GET_NUM

# --- دالة إنشاء الكود (بعد إرسال الرقم) ---
async def create_vless(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit = update.message.text
    if not limit.isdigit():
        await update.message.reply_text("الرجاء إرسال رقم صحيح.")
        return GET_NUM

    try:
        # 1. توليد UUID وجلب IP السيرفر
        uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
        ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        
        # 2. فتح إعدادات Xray وإضافة المستخدم
        config_path = "/usr/local/etc/xray/config.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # تنسيق الإيميل مهم جداً للمراقب: limit_العدد_أول4حروف
        email = f"limit_{limit}_{uuid[:4]}"
        
        # إضافة المستخدم للقائمة
        config['inbounds'][0]['settings']['clients'].append({
            "id": uuid,
            "email": email
        })
        
        # 3. حفظ الإعدادات وإعادة تشغيل Xray
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        
        os.system("systemctl restart xray")
        
        # 4. توليد رابط الـ VLESS
        # نستخدم بورت 80 ومسار /myvless كما هو محدد في ملف install.sh
        link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{limit}"
        
        await update.message.reply_text(f"✅ تم إنشاء كود جديد!\n\n👤 المستخدم: `{email}`\n🔢 الحد: {limit} أجهزة\n\n`{link}`")
        
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ أثناء الإضافة: {e}")
    
    return ConversationHandler.END

if __name__ == '__main__':
    # بناء البوت
    app = Application.builder().token(TOKEN).build()

    # إعداد نظام المحادثة (الاسم الصحيح هو ConversationHandler)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add", start_add)],
        states={
            GET_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_vless)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    print("البوت يعمل الآن ومستعد لإصدار الأكواد...")
    app.run_polling()
