import os, subprocess, json, sys, time, uuid, random, string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

# إعداد المسارات
sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except ImportError:
    print("❌ خطأ: ملف config.py غير موجود!")
    sys.exit()

FILES = {
    "prods": "/etc/my-v2ray/products.json",
    "users": "/etc/my-v2ray/users.json",
    "xray": "/usr/local/etc/xray/config.json"
}

# تعريف مراحل المحادثة (الأسئلة)
(NAME, PROTOCOL, PORT, ADDRESS_CHOICE, ADDRESS_INPUT, UUID_CHOICE, UUID_INPUT, 
 PATH_CHOICE, PATH_INPUT, HOST_CHOICE, HOST_INPUT, PRICE) = range(12)

# --- دوال المساعدة (Helper Functions) ---

def load_json(path):
    if not os.path.exists(path): return {}
    with open(path, 'r') as f: return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

def restart_xray():
    os.system("systemctl restart xray")

# --- دالة تهيئة البورت (النسخة التي تسمح بالتعدد) ---
def ensure_port_config(protocol, port):
    config = load_json(FILES['xray'])
    port = int(port)
    
    # فحص إذا كان البروتوكول موجود مسبقاً على هذا البورت
    for ib in config.get('inbounds', []):
        if ib.get('port') == port and ib.get('protocol') == protocol:
            return True, f"✅ بروتوكول {protocol} مفعل مسبقاً على بورت {port}."

    # إذا لم يكن موجوداً، نقوم بإضافته كمدخل جديد بنفس البورت
    new_ib = {
        "port": port,
        "protocol": protocol,
        "settings": {"clients": []} if protocol != "shadowsocks" else {"users": [], "method": "chacha20-ietf-poly1305"},
        "streamSettings": {
            "network": "ws",
            "wsSettings": { "path": f"/{protocol}_{random.randint(100,999)}" }
        },
        "tag": f"inbound_{port}_{protocol}_{random.randint(1000,9999)}"
    }
    if protocol == "vless": new_ib["settings"]["decryption"] = "none"
    
    config['inbounds'].append(new_ib)
    save_json(FILES['xray'], config)
    restart_xray()
    return True, f"✅ تم دمج {protocol} بنجاح على بورت {port}."

# --- أوامر البوت الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == int(ADMIN_ID):
        kb = [["➕ إضافة منتج", "📊 مراقبة السيرفر"], ["🛒 المتجر", "🔄 ريستارت Xray"]]
        await update.message.reply_text("🛠️ لوحة تحكم الإدارة:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        kb = [["🛍️ شراء كود", "💰 رصيدي"]]
        await update.message.reply_text("مرحباً بك في المتجر التلقائي:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- معالج إضافة منتج (خطوة بخطوة) ---

async def add_prod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return ConversationHandler.END
    await update.message.reply_text("1️⃣ اسم المنتج (مثلاً: تروجان بريميوم):", reply_markup=ReplyKeyboardMarkup([["🔙 إلغاء"]], resize_keyboard=True))
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_name'] = update.message.text
    kb = [["vless", "vmess"], ["trojan", "shadowsocks"]]
    await update.message.reply_text("2️⃣ اختر البروتوكول:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return PROTOCOL

async def get_protocol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    await update.message.reply_text("3️⃣ رقم البورت (مثلاً 80):")
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    port = update.message.text
    proto = context.user_data['p_proto']
    # تشغيل دالة الدمج الذكية
    ok, msg = ensure_port_config(proto, port)
    context.user_data['p_port'] = port
    await update.message.reply_text(f"{msg}\n\n4️⃣ العنوان (Address):", reply_markup=ReplyKeyboardMarkup([["📍 تلقائي IP"], ["✏️ يدوي"]], resize_keyboard=True))
    return ADDRESS_CHOICE

async def get_addr_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "تلقائي" in update.message.text:
        context.user_data['p_addr'] = "AUTO"
        return await ask_uuid(update, context)
    await update.message.reply_text("اكتب الـ IP أو الدومين:")
    return ADDRESS_INPUT

async def get_addr_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_addr'] = update.message.text
    return await ask_uuid(update, context)

async def ask_uuid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("5️⃣ نظام UUID / الباسورد:", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"], ["✏️ يدوي"]], resize_keyboard=True))
    return UUID_CHOICE

async def get_uuid_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_uuid'] = "RANDOM"
        return await ask_path(update, context)
    await update.message.reply_text("اكتب الكود يدوي:")
    return UUID_INPUT

async def get_uuid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_uuid'] = update.message.text
    return await ask_path(update, context)

async def ask_path(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("6️⃣ المسار (Path):", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"], ["✏️ يدوي"]], resize_keyboard=True))
    return PATH_CHOICE

async def get_path_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_path'] = "/" + "".join(random.choices(string.ascii_lowercase, k=6))
        return await ask_host(update, context)
    await update.message.reply_text("اكتب المسار (مثال /speed):")
    return PATH_INPUT

async def get_path_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = update.message.text
    context.user_data['p_path'] = p if p.startswith("/") else "/" + p
    return await ask_host(update, context)

async def ask_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("7️⃣ الـ Host (اختياري):", reply_markup=ReplyKeyboardMarkup([["❌ تخطي"], ["✏️ يدوي"]], resize_keyboard=True))
    return HOST_CHOICE

async def get_host_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "تخط" in update.message.text:
        context.user_data['p_host'] = ""
    else:
        await update.message.reply_text("اكتب الـ Host:")
        return HOST_INPUT
    await update.message.reply_text("8️⃣ السعر بالنقاط:")
    return PRICE

async def get_host_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_host'] = update.message.text
    await update.message.reply_text("8️⃣ السعر بالنقاط:")
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
            "host": context.user_data['p_host'], "price": price
        }
        save_json(FILES['prods'], prods)
        await update.message.reply_text("✅ تم حفظ المنتج!", reply_markup=ReplyKeyboardMarkup([["🛒 المتجر"]], resize_keyboard=True))
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ أرقام فقط!")
        return PRICE

# --- نظام الشراء (توليد الكود) ---

async def shop_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prods = load_json(FILES['prods'])
    if not prods:
        await update.message.reply_text("المتجر فارغ.")
        return
    for pid, p in prods.items():
        kb = [[InlineKeyboardButton(f"شراء ({p['price']}💰)", callback_data=f"buy_{pid}")]]
        await update.message.reply_text(f"📦 المنتج: {p['name']}\n🚀 النوع: {p['proto']}\n🔌 البورت: {p['port']}", reply_markup=InlineKeyboardMarkup(kb))

async def process_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split("_")[1]
    p = load_json(FILES['prods']).get(pid)
    uid = str(query.from_user.id)
    users = load_json(FILES['users'])
    
    if users.get(uid, {}).get("points", 0) < p['price']:
        await query.answer("❌ رصيدك غير كافٍ!", show_alert=True); return

    await query.answer("⏳ جاري إنشاء الحساب...")
    
    # تفاصيل العميل
    f_uuid = str(uuid.uuid4()) if p['uuid'] == "RANDOM" else p['uuid']
    f_addr = subprocess.getoutput("curl -s ifconfig.me") if p['addr'] == "AUTO" else p['addr']
    
    # تحديث Xray
    config = load_json(FILES['xray'])
    for ib in config['inbounds']:
        if str(ib['port']) == str(p['port']) and ib['protocol'] == p['proto']:
            email = f"u_{uid}_{random.randint(100,999)}"
            if p['proto'] == "shadowsocks":
                ib['settings']['users'].append({"password": f_uuid, "email": email})
            else:
                key = "password" if p['proto'] == "trojan" else "id"
                ib['settings']['clients'].append({key: f_uuid, "email": email})
            # ملاحظة: في WS التعدد يكون عبر إضافة المستخدم لنفس المدخل الذي يحمل المسار
            # إذا كان هناك عدة منتجات بنفس البورت والبروتوكول، سيتم الإضافة للمدخل الأول المطابق
            break
            
    save_json(FILES['xray'], config)
    restart_xray()
    
    # خصم النقاط
    users[uid]['points'] -= p['price']
    save_json(FILES['users'], users)
    
    # توليد الرابط
    link = ""
    name = p['name'].replace(" ", "_")
    if p['proto'] == "vless":
        link = f"vless://{f_uuid}@{f_addr}:{p['port']}?type=ws&security=none&path={p['path']}&host={p['host']}#{name}"
    elif p['proto'] == "trojan":
        link = f"trojan://{f_uuid}@{f_addr}:{p['port']}?type=ws&security=none&path={p['path']}&host={p['host']}#{name}"
    elif p['proto'] == "vmess":
        vj = {"v":"2","ps":name,"add":f_addr,"port":p['port'],"id":f_uuid,"aid":"0","net":"ws","path":p['path'],"host":p['host'],"tls":"none"}
        link = "vmess://" + subprocess.getoutput(f"echo '{json.dumps(vj)}' | base64 -w 0")
    
    await query.message.reply_text(f"✅ تم الشراء!\n\n`{link}`", parse_mode='Markdown')

# --- تشغيل ---

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة منتج"), add_prod_start)],
        states={
            NAME: [MessageHandler(filters.TEXT, get_name)],
            PROTOCOL: [MessageHandler(filters.TEXT, get_protocol)],
            PORT: [MessageHandler(filters.TEXT, get_port)],
            ADDRESS_CHOICE: [MessageHandler(filters.TEXT, get_addr_choice)],
            ADDRESS_INPUT: [MessageHandler(filters.TEXT, get_addr_input)],
            UUID_CHOICE: [MessageHandler(filters.TEXT, get_uuid_choice)],
            UUID_INPUT: [MessageHandler(filters.TEXT, get_uuid_input)],
            PATH_CHOICE: [MessageHandler(filters.TEXT, get_path_choice)],
            PATH_INPUT: [MessageHandler(filters.TEXT, get_path_input)],
            HOST_CHOICE: [MessageHandler(filters.TEXT, get_host_choice)],
            HOST_INPUT: [MessageHandler(filters.TEXT, get_host_input)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
        }, fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^🛒 المتجر|^🛍️ شراء"), shop_list))
    app.add_handler(CallbackQueryHandler(process_buy, pattern="^buy_"))
    
    print("🚀 البوت يعمل بنظام الدمج المطور...")
    app.run_polling()

if __name__ == '__main__': main()
