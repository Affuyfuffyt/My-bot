import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationRouter, ContextTypes

# تحميل الإعدادات (التوكن والأيدي)
sys.path.append('/etc/my-v2ray')
from config import TOKEN, ADMIN_ID

# مسار ملف إعدادات السيرفر
CONFIG_PATH = "/usr/local/etc/xray/config.json"

# تعريف حالة "انتظار رقم الأجهزة"
AWAITING_LIMIT = 1

# 1. الدالة التي تعمل عند كتابة /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("👋 أهلاً بك يا مدير! استعمل /add لعمل كود جديد.")

# 2. الدالة التي تبدأ عند كتابة /add (تطلب الرقم)
async def ask_for_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("كم جهازاً تريد أن يعمل على هذا الكود؟ (أرسل الرقم فقط)")
    return AWAITING_LIMIT  # هنا البوت يدخل في "حالة انتظار"

# 3. الدالة التي تأخذ الرقم وتصنع الكود
async def finish_and_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_limit = update.message.text
    
    # التأكد أن المستخدم أرسل رقماً وليس كلاماً
    if not user_limit.isdigit():
        await update.message.reply_text("من فضلك أرسل رقماً فقط (مثل 1 أو 2).")
        return AWAITING_LIMIT

    # بناء الكود
    uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
    ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    
    # إضافة البيانات لملف السيرفر
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    # نضع الرقم في خانة الإيميل (ليعرفه سكريبت المراقبة)
    user_email = f"limit_{user_limit}_{uuid[:4]}@bot.com"
    config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": user_email})
    
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)
    
    # إعادة تشغيل السيرفر لتفعيل المستخدم الجديد
    os.system("systemctl restart xray")
    
    # إرسال الرابط النهائي
    link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{user_limit}"
    await update.message.reply_text(f"✅ تم بنجاح!\nالحد الأقصى: {user_limit} أجهزة.\n\n`{link}`")
    
    return ConversationRouter.END  # إنهاء المحادثة والعودة للوضع الطبيعي

# تشغيل البوت
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()

    # إعداد نظام "المحادثة"
    conv_handler = ConversationRouter(
        entry_points=[CommandHandler("add", ask_for_limit)],
        states={
            AWAITING_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_and_create)]
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    
    print("البوت بدأ العمل...")
    app.run_polling()
