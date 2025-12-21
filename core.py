import os, subprocess, sys, json
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
from config import TOKEN, ADMIN_ID

CONFIG_PATH = "/usr/local/etc/xray/config.json"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 البوت يعمل بنجاح!\n/add - إنشاء حساب VLESS WS")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    
    uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
    ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    
    # إضافة المستخدم للملف
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    # هنا Email يحمل علامة الـ Limit (مثلاً 1 متصل)
    config['inbounds'][0]['settings']['clients'].append({
        "id": uuid, 
        "email": f"limit1_{uuid[:4]}@vps.com"
    })
    
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)
    
    # تحديث الإعدادات بدون ريستارت كامل (Soft Reload)
    os.system("systemctl reload xray")
    
    link = f"vless://{uuid}@{ip}:443?path=%2Fmyvless&security=none&encryption=none&type=ws#VLESS_WS"
    
    await update.message.reply_text(f"✅ تم إنشاء الحساب:\n\n`{link}`", parse_mode='Markdown')

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.run_polling()
