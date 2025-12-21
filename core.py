import os, subprocess, json, sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes

# التحميل من config
sys.path.append('/etc/my-v2ray')
from config import TOKEN, ADMIN_ID

GET_NUM, GET_QUOTA = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("🚀 أرسل /add لإنشاء كود جديد.")

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("1️⃣ كم جهازاً تريد السماح به؟ (رقم فقط)")
    return GET_NUM

async def get_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['limit'] = update.message.text
    await update.message.reply_text("2️⃣ أدخل سعة البيانات (مثال: 1G أو 500M):")
    return GET_QUOTA

async def create_vless(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quota_input = update.message.text.upper()
    limit = context.user_data['limit']
    
    # تحويل السعة إلى Bytes
    try:
        num = int(''.join(filter(str.isdigit, quota_input)))
        if "G" in quota_input: bytes_limit = num * 1024 * 1024 * 1024
        else: bytes_limit = num * 1024 * 1024
    except:
        await update.message.reply_text("⚠️ خطأ في صيغة السعة. جرب 1G.")
        return GET_QUOTA

    uuid = subprocess.check_output("xray uuid", shell=True).decode().strip()
    ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    
    # الإيميل يحمل كل المعلومات: limit_الأجهزة_max_الجيجات_uuid
    email = f"limit_{limit}_max_{bytes_limit}_{uuid[:4]}"
    
    # إضافة لملف Xray
    config_path = "/usr/local/etc/xray/config.json"
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": email})
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    
    os.system("systemctl restart xray")
    
    link = f"vless://{uuid}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#Limit_{limit}_{quota_input}"
    
    await update.message.reply_text(f"✅ تم الإنشاء!\n\n👥 الأجهزة: {limit}\n💾 السعة: {quota_input}\n\n`{link}`")
    return ConversationHandler.END

# (باقي كود الـ Application والـ Handlers كما في النسخ السابقة)
