import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationRouter

# 1. ربط الإعدادات
sys.path.append('/etc/my-v2ray')
from config import TOKEN, ADMIN_ID

CONFIG_PATH = "/usr/local/etc/xray/config.json"
# تعريف مرحلة "انتظار الرقم"
WAITING_FOR_LIMIT = 1

# --- دالة البداية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 أهلاً بك! استخدم /add لإنشاء كود جديد.")

# --- عندما تضغط /add (تبدأ المحادثة) ---
async def add_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("كم جهازاً تريد أن يعمل على هذا الكود؟ (أرسل رقم فقط)")
    return WAITING_FOR_LIMIT # هنا البوت يدخل في حالة "الانتظار"

# --- عندما ترسل الرقم (تكتمل المحادثة) ---
async def process_limit_and_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text # هذا هو الرقم الذي أرسلته أنت
    
    if not user_input.isdigit():
        await update.message.reply_text("خطأ! أرسل رقماً فقط (مثلاً 1 أو 2).")
        return WAITING_FOR_LIMIT

    # الآن ينفذ بناء الكود بعدما عرف الرقم
    uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
    ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    # نضع الرقم داخل الإيميل ليعرفه سكريبت المراقبة
    user_email = f"limit_{user_input}_{uuid[:4]}@bot.com"
    config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": user_email})
    
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)
    
    os.system("systemctl restart xray")
    
    link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{user_input}"
    
    await update.message.reply_text(f"✅ تم إنشاء كود لـ {user_input} أجهزة:\n\n`{link}`")
    return ConversationRouter.END # إنهاء الجلسة والرجوع للحالة الطبيعية

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    # إعداد نظام المحادثة
    conv_handler = ConversationRouter(
        entry_points=[CommandHandler("add", add_command_start)],
        states={
            WAITING_FOR_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_limit_and_create)]
        },
        fallbacks=[]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.run_polling()
