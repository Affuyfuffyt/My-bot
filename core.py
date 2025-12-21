import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ربط الإعدادات
sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except ImportError:
    sys.exit(1)

CONFIG_PATH = "/usr/local/etc/xray/config.json"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 البوت متصل الآن بنجاح!\n/add - إنشاء حساب VLESS WS")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    
    try:
        uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
        ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        # إضافة المستخدم
        config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": f"{uuid[:4]}@bot.com"})
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        
        # الحل البديل للـ Reload لضمان عدم الانقطاع
        os.system("systemctl restart xray") 
        
        link = f"vless://{uuid}@{ip}:443?path=%2Fmyvless&security=none&encryption=none&type=ws#VLESS_WS"
        await update.message.reply_text(f"✅ تم إنشاء الحساب:\n\n`{link}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ حدث خطأ: {e}")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.run_polling()
