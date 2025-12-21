import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationRouter

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except ImportError:
    sys.exit(1)

CONFIG_PATH = "/usr/local/etc/xray/config.json"
GET_LIMIT = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 أهلاً بك! استخدم أمر /add لإنشاء كود جديد وتحديد عدد الأجهزة.")

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("كم عدد الأجهزة المسموح بها لهذا الكود؟ (أرسل رقم فقط)")
    return GET_LIMIT

async def create_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit = update.message.text
    if not limit.isdigit():
        await update.message.reply_text("الرجاء إرسال رقم صحيح (مثل 1 أو 2).")
        return GET_LIMIT

    try:
        uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
        ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        user_email = f"limit_{limit}_{uuid[:4]}@bot.com"
        config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": user_email})
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        
        os.system("systemctl restart xray")
        
        link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{limit}_{uuid[:4]}"
        
        await update.message.reply_text(f"✅ تم!\nعدد الأجهزة: {limit}\nالرابط:\n`{link}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")
    
    return ConversationRouter.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم إلغاء العملية.")
    return ConversationRouter.END

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationRouter(
        entry_points=[CommandHandler("add", add_start)],
        states={GET_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_link)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.run_polling()
