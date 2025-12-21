import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationRouter, ContextTypes

# إخبار البوت بمكان ملف الإعدادات
sys.path.append('/etc/my-v2ray')
from config import TOKEN, ADMIN_ID

# تحديد المراحل (مرحلة سؤال الأدمن عن الرقم)
STEP_LIMIT = 1

# --- 1. البداية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("👋 البوت يعمل! أرسل /add للبدء.")

# --- 2. السؤال (عند الضغط على add) ---
async def ask_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("كم عدد الأجهزة المسموح بها لهذا الكود؟")
    return STEP_LIMIT # هنا البوت يفتح "أذنه" وينتظر الرقم

# --- 3. التنفيذ (بعد إرسال الرقم) ---
async def finish_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text
    if not number.isdigit():
        await update.message.reply_text("أرجوك أرسل رقماً فقط!")
        return STEP_LIMIT

    # هنا نصنع الكود (VLESS)
    uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
    ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    
    # نعدل ملف الـ config الخاص بالسيرفر
    with open("/usr/local/etc/xray/config.json", 'r') as f:
        config = json.load(f)
    
    # نضع الرقم داخل الايميل ليقرأه سكريبت المراقبة لاحقاً
    email = f"limit_{number}_{uuid[:4]}@bot.com"
    config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": email})
    
    with open("/usr/local/etc/xray/config.json", 'w') as f:
        json.dump(config, f, indent=4)
    
    os.system("systemctl restart xray") # حفظ وتفعيل
    
    # صنع الرابط
    link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{number}"
    await update.message.reply_text(f"✅ تم! الحد: {number}\n\n`{link}`")
    
    return ConversationRouter.END # إغلاق المحادثة

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    # نظام الردود الذكي (Conversation)
    my_conv = ConversationRouter(
        entry_points=[CommandHandler("add", ask_limit)],
        states={STEP_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_and_send)]},
        fallbacks=[]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(my_conv)
    app.run_polling()
