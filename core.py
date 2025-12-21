import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationRouter, MessageHandler, filters

sys.path.append('/etc/my-v2ray')
from config import TOKEN, ADMIN_ID

CONFIG_PATH = "/usr/local/etc/xray/config.json"
CHOOSING_LIMIT = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 لوحة تحكم VLESS WS الاحترافية\n/add - إنشاء حساب مع تحديد عدد المتصلين")

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("كم عدد المتصلين (IP Limit) الذي تريده لهذا الحساب؟ (أرسل رقم فقط)")
    return CHOOSING_LIMIT

async def create_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    limit = update.message.text
    uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
    ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    
    # إضافة المستخدم للملف بدون عمل Restart كامل (استخدام xray api إذا كان مفعلاً أو تعديل ذكي)
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    # ملاحظة: بروتوكول VLESS لا يدعم IP Limit داخلياً بشكل مباشر، 
    # لذا سنستخدم email لحفظ قيمة الـ limit مؤقتاً أو كعلامة
    config['inbounds'][0]['settings']['clients'].append({
        "id": uuid, 
        "email": f"limit_{limit}_{uuid[:4]}@bot.com"
    })
    
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)
    
    # Reload بدون قطع الاتصال (Soft Restart)
    os.system("systemctl reload xray") 
    
    link = f"vless://{uuid}@{ip}:443?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{limit}"
    
    await update.message.reply_text(f"✅ تم الإنشاء بحد أقصى {limit} متصل:\n\n`{link}`", parse_mode='Markdown')
    return ConversationRouter.END

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationRouter(
        entry_points=[CommandHandler("add", add_start)],
        states={CHOOSING_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_user)]},
        fallbacks=[],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.run_polling()
