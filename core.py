import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
from config import TOKEN, ADMIN_ID

CONFIG_PATH = "/usr/local/etc/xray/config.json"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 البوت جاهز (بورت 80)\n/add - إنشاء كود VLESS WS")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    
    try:
        uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
        ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
        config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": f"u_{uuid[:4]}@bot.com"})
        
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        
        os.system("systemctl restart xray")
        
        # الرابط الجديد ببورت 80
        link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#VLESS_B80"
        
        await update.message.reply_text(f"✅ تم الإنشاء ببورت 80:\n\n`{link}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.run_polling()
