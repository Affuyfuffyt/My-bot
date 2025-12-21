import os, subprocess, sys
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except ImportError:
    sys.exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 أهلاً بك يا أدمن! البوت يعمل.\nاستخدم /add لإنشاء حساب.")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
    ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    link = f"vless://{uuid}@{ip}:443?encryption=none&security=none&type=tcp#NewUser"
    await update.message.reply_text(f"✅ تم!\nالرابط:\n`{link}`", parse_mode='Markdown')

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_user))
    app.run_polling()
