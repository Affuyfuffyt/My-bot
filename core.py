import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

# ربط ملف الإعدادات
sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except ImportError:
    print("Error: config.py not found")
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
    await update.message.reply_text("كم جهازاً تريد أن يعمل على هذا الكود؟ (أرسل رقم فقط)")
    return GET_NUM

# --- دالة إنشاء الكود (بعد إرسال الرقم) ---
async def create_vless(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit = update.message.text
    if not limit.isdigit():
        await update.message.reply_text("الرجاء إرسال رقم صحيح.")
        return GET_NUM

    try:
        uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
        ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        
        with open("/usr/local/etc/xray/config.json", 'r') as f:
            config = json.load(f)
        
        email = f"limit_{limit}_{uuid[:4]}@bot.com"
        config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": email})
        
        with open("/usr/local/etc/xray/config.json", 'w') as f:
            json.dump(config, f, indent=4)
        
        os.system("systemctl restart xray")
        
        link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{limit}"
        await update.message.reply_text(f"✅ تم إنشاء كود لـ {limit} أجهزة:\n\n`{link}`")
        
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")
    
    return ConversationHandler.END

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()

    # استخدام الاسم الصحيح: ConversationHandler
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", start_add)],
        states={GET_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_vless)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    
    print("البوت بدأ العمل الآن...")
    app.run_polling()
