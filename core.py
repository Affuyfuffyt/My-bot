import os, subprocess, json, sys, time, uuid, random, string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

# إعداد المسارات
sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except: sys.exit("❌ Config.py missing!")

FILES = {"prods": "/etc/my-v2ray/products.json", "users": "/etc/my-v2ray/users.json", "xray": "/usr/local/etc/xray/config.json"}

# مراحل المحادثة
(NAME, PROTOCOL, PORT, ADDRESS_CHOICE, ADDRESS_INPUT, UUID_CHOICE, UUID_INPUT, PATH_CHOICE, PATH_INPUT, HOST_CHOICE, HOST_INPUT, PRICE) = range(12)

def load_json(p):
    try:
        with open(p, 'r') as f: return json.load(f)
    except: return {}

def save_json(p, d):
    with open(p, 'w') as f: json.dump(d, f, indent=4)

def restart_xray():
    os.system("systemctl restart xray")

# --- الدالة المعدلة (لا تعطي خطأ أبداً) ---
def force_add_port(protocol, port):
    config = load_json(FILES['xray'])
    port = int(port)
    
    # إنشاء Inbound جديد بـ Tag فريد (هذا يسمح بتكرار البورت 80)
    tag_name = f"tag_{port}_{protocol}_{"".join(random.choices(string.digits, k=4))}"
    
    new_ib = {
        "port": port,
        "protocol": protocol,
        "settings": {"clients": []} if protocol != "shadowsocks" else {"users": [], "method": "chacha20-ietf-poly1305"},
        "streamSettings": {
            "network": "ws",
            "wsSettings": { "path": f"/{protocol}_{random.randint(100,999)}" }
        },
        "tag": tag_name
    }
    
    if protocol == "vless": new_ib["settings"]["decryption"] = "none"
    if protocol == "trojan": new_ib["settings"] = {"clients": []}
    
    if 'inbounds' not in config: config['inbounds'] = []
    config['inbounds'].append(new_ib)
    
    save_json(FILES['xray'], config)
    restart_xray()
    return True, f"✅ تم تثبيت بروتوكول {protocol} على بورت {port} بنجاح."

# --- بقية الكود (معدل ليتوافق مع الإضافة القسرية) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == int(ADMIN_ID):
        kb = [["➕ إضافة منتج", "📊 المراقبة"], ["🛒 المتجر", "🔄 ريستارت Xray"]]
        await update.message.reply_text("🛠️ لوحة الإدارة:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        await update.message.reply_text("مرحباً بك في المتجر.", reply_markup=ReplyKeyboardMarkup([["🛍️ المتجر"]], resize_keyboard=True))

async def add_prod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1️⃣ اسم المنتج:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_name'] = update.message.text
    await update.message.reply_text("2️⃣ البروتوكول:", reply_markup=ReplyKeyboardMarkup([["vless", "vmess"], ["trojan", "shadowsocks"]], resize_keyboard=True))
    return PROTOCOL

async def get_proto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    await update.message.reply_text("3️⃣ رقم البورت (مثلاً 80):")
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    port = update.message.text
    proto = context.user_data['p_proto']
    # استخدام الدالة الجديدة التي لا ترفض البورت
    ok, msg = force_add_port(proto, port)
    context.user_data['p_port'] = port
    await update.message.reply_text(f"{msg}\n\n4️⃣ العنوان:", reply_markup=ReplyKeyboardMarkup([["📍 تلقائي IP"], ["✏️ يدوي"]], resize_keyboard=True))
    return ADDRESS_CHOICE

async def get_addr_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "تلقائي" in update.message.text:
        context.user_data['p_addr'] = "AUTO"
        await update.message.reply_text("5️⃣ UUID:", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"]], resize_keyboard=True))
        return UUID_CHOICE
    await update.message.reply_text("اكتب العنوان:"); return ADDRESS_INPUT

async def get_addr_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_addr'] = update.message.text
    await update.message.reply_text("5️⃣ UUID:", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"]], resize_keyboard=True))
    return UUID_CHOICE

async def get_uuid_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_uuid'] = "RANDOM" if "عشوائي" in update.message.text else update.message.text
    await update.message.reply_text("6️⃣ المسار (Path):", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"]], resize_keyboard=True))
    return PATH_CHOICE

async def get_path_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_path'] = "/" + "".join(random.choices(string.ascii_lowercase, k=6))
    else: context.user_data['p_path'] = update.message.text
    await update.message.reply_text("7️⃣ السعر بالنقاط:")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text)
        prods = load_json(FILES['prods'])
        pid = str(uuid.uuid4())[:8]
        prods[pid] = {
            "name": context.user_data['p_name'], "proto": context.user_data['p_proto'],
            "port": context.user_data['p_port'], "addr": context.user_data['p_addr'],
            "uuid": context.user_data['p_uuid'], "path": context.user_data['p_path'],
            "price": price, "host": ""
        }
        save_json(FILES['prods'], prods)
        await update.message.reply_text("✅ تم الحفظ بنجاح!")
        return ConversationHandler.END
    except: return PRICE

# --- نظام الشراء (توليد الروابط) ---
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prods = load_json(FILES['prods'])
    for pid, p in prods.items():
        kb = [[InlineKeyboardButton("شراء", callback_data=f"buy_{pid}")]]
        await update.message.reply_text(f"📦 {p['name']} | 💰 {p['price']}", reply_markup=InlineKeyboardMarkup(kb))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split("_")[1]
    p = load_json(FILES['prods']).get(pid)
    uid = str(query.from_user.id)
    
    f_uuid = str(uuid.uuid4()) if p['uuid'] == "RANDOM" else p['uuid']
    f_addr = subprocess.getoutput("curl -s ifconfig.me") if p['addr'] == "AUTO" else p['addr']
    
    # تحديث Xray
    config = load_json(FILES['xray'])
    for ib in config['inbounds']:
        if str(ib['port']) == str(p['port']) and ib['protocol'] == p['proto']:
            if p['proto'] == "shadowsocks":
                ib['settings']['users'].append({"password": f_uuid, "email": f"u_{uid}"})
            else:
                key = "password" if p['proto'] == "trojan" else "id"
                ib['settings']['clients'].append({key: f_uuid, "email": f"u_{uid}"})
            # تثبيت المسار لهذا العميل
            ib['streamSettings']['wsSettings']['path'] = p['path']
            break
    
    save_json(FILES['xray'], config)
    restart_xray()
    
    link = f"{p['proto']}://{f_uuid}@{f_addr}:{p['port']}?type=ws&security=none&path={p['path']}#Shop"
    await query.message.reply_text(f"✅ كودك:\n`{link}`", parse_mode='Markdown')

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة منتج"), add_prod_start)],
        states={
            NAME: [MessageHandler(filters.TEXT, get_name)],
            PROTOCOL: [MessageHandler(filters.TEXT, get_proto)],
            PORT: [MessageHandler(filters.TEXT, get_port)],
            ADDRESS_CHOICE: [MessageHandler(filters.TEXT, get_addr_choice)],
            ADDRESS_INPUT: [MessageHandler(filters.TEXT, get_addr_input)],
            UUID_CHOICE: [MessageHandler(filters.TEXT, get_uuid_choice)],
            PATH_CHOICE: [MessageHandler(filters.TEXT, get_path_choice)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
        }, fallbacks=[]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^🛒 المتجر"), shop))
    app.add_handler(CallbackQueryHandler(buy, pattern="^buy_"))
    app.run_polling()

if __name__ == '__main__': main()
