import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except ImportError:
    sys.exit(1)

CONFIG_PATH = "/usr/local/etc/xray/config.json"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 أهلاً بك! بوت الإدارة يعمل (Port 80)\n\n/add - لإنشاء كود VLESS WS جديد")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    
    try:
        uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
        ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        
        # إضافة المستخدم للإعدادات
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # وضع إيميل فريد ليعرفه سكريبت المراقبة
        user_email = f"u_{uuid[:4]}@bot.com"
        config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": user_email})
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        
        # تحديث سريع للمحرك
        os.system("systemctl restart xray")
        
        # توليد الرابط
        link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#User_{uuid[:4]}"
        
        await update.message.reply_text(f"✅ تم إنشاء كود جديد:\n\n`{link}`", parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ تقني: {e}")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.run_polling()
