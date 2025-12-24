import os, subprocess, json, sys, time, uuid, random, string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except: sys.exit("❌ Config.py missing!")

FILES = {"prods": "/etc/my-v2ray/products.json", "users": "/etc/my-v2ray/users.json", "xray": "/usr/local/etc/xray/config.json"}

# مراحل المحادثة
(NAME, DESC, MEDIA, PROTOCOL, PORT, ADDRESS_CHOICE, ADDRESS_INPUT, UUID_CHOICE, UUID_INPUT, PATH_CHOICE, PATH_INPUT, HOST_CHOICE, HOST_INPUT, SNI_CHOICE, SNI_INPUT, LIMIT, QUOTA, DURATION, PRICE) = range(19)

def load_json(path):
    try:
        with open(path, 'r') as f: return json.load(f)
    except: return {}

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

def restart_xray():
    os.system("systemctl restart xray")

# --- دالة إدارة البورتات الذكية ---
def setup_inbound_on_xray(protocol, port):
    config = load_json(FILES['xray'])
    port = int(port)
    
    # البحث هل البورت موجود مسبقاً؟
    for ib in config['inbounds']:
        if ib.get('port') == port:
            if ib['protocol'] == protocol:
                return True, f"✅ البورت {port} موجود مسبقاً لنفس البروتوكول."
            else:
                return False, f"⚠️ البورت {port} مشغول ببروتوكول {ib['protocol']}. يجب استخدام بورت آخر أو مسحه."

    # إذا البورت جديد، ننشئ الهيكل الأساسي
    new_ib = {
        "port": port,
        "protocol": protocol,
        "settings": {"clients": []} if protocol != "shadowsocks" else {"users": [], "method": "chacha20-ietf-poly1305"},
        "streamSettings": {
            "network": "ws",
            "wsSettings": {"path": "/"} # المسار الافتراضي، سيتم تخصيصه عند الشراء
        },
        "tag": f"inbound_{port}_{protocol}"
    }
    
    # إضافات خاصة لكل بروتوكول
    if protocol == "vless": new_ib["settings"]["decryption"] = "none"
    if protocol == "trojan": new_ib["settings"]["clients"] = []
    
    config['inbounds'].append(new_ib)
    save_json(FILES['xray'], config)
    restart_xray()
    return True, f"✅ تم فتح بورت {port} جديد لبروتوكول {protocol}."

# --- البداية والقوائم ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == int(ADMIN_ID):
        kb = [["➕ إضافة منتج", "🛒 المنتجات"], ["👥 المستخدمين", "🔄 ريستارت Xray"]]
        await update.message.reply_text("🛠️ لوحة التحكم الاحترافية:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        kb = [["🛍️ المتجر", "💰 رصيدي"], ["🆘 الدعم الفني"]]
        await update.message.reply_text("مرحباً بك في بوت البيع التلقائي:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- خطوات إضافة المنتج (نفس معالجك المطلوب) ---
async def add_prod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("1️⃣ اسم المنتج:", reply_markup=ReplyKeyboardMarkup([["🔙 إلغاء"]], resize_keyboard=True))
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_name'] = update.message.text
    await update.message.reply_text("2️⃣ اختر البروتوكول:", reply_markup=ReplyKeyboardMarkup([["vless", "vmess"], ["trojan", "shadowsocks"]], resize_keyboard=True))
    return PROTOCOL

async def get_proto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    await update.message.reply_text("3️⃣ رقم البورت (مثلاً 80 أو 443):")
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    port = update.message.text
    proto = context.user_data['p_proto']
    success, msg = setup_inbound_on_xray(proto, port)
    if not success:
        await update.message.reply_text(msg)
        return PORT
    context.user_data['p_port'] = port
    await update.message.reply_text(f"{msg}\n\n4️⃣ العنوان (Address):", reply_markup=ReplyKeyboardMarkup([["📍 تلقائي IP"], ["✏️ يدوي"]], resize_keyboard=True))
    return ADDRESS_CHOICE

async def get_addr_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "تلقائي" in update.message.text:
        context.user_data['p_addr'] = "AUTO"
        return await ask_uuid(update, context)
    await update.message.reply_text("اكتب العنوان (IP أو دومين):")
    return ADDRESS_INPUT

async def get_addr_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_addr'] = update.message.text
    return await ask_uuid(update, context)

async def ask_uuid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("5️⃣ الـ UUID/Password:", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"], ["✏️ يدوي"]], resize_keyboard=True))
    return UUID_CHOICE

async def get_uuid_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_uuid'] = "RANDOM"
        return await ask_path(update, context)
    await update.message.reply_text("اكتب الـ UUID أو الباسورد يدوي:")
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
    await update.message.reply_text("اكتب المسار (مثال: /vless):")
    return PATH_INPUT

async def get_path_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_path'] = update.message.text if update.message.text.startswith("/") else "/" + update.message.text
    return await ask_host(update, context)

async def ask_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("7️⃣ الـ Host:", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"], ["✏️ يدوي"], ["❌ تخطي"]], resize_keyboard=True))
    return HOST_CHOICE

async def get_host_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if "تخطي" in choice: context.user_data['p_host'] = ""
    elif "عشوائي" in choice: context.user_data['p_host'] = "speedtest.net"
    else: 
        await update.message.reply_text("اكتب الـ Host:"); return HOST_INPUT
    return await ask_sni(update, context)

async def get_host_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_host'] = update.message.text
    return await ask_sni(update, context)

async def ask_sni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data['p_port'] == "443":
        await update.message.reply_text("8️⃣ الـ SNI (لبورت 443):", reply_markup=ReplyKeyboardMarkup([["❌ فارغ"], ["✏️ يدوي"]], resize_keyboard=True))
        return SNI_CHOICE
    context.user_data['p_sni'] = ""
    return await ask_final(update, context)

async def get_sni_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "فارغ" in update.message.text: context.user_data['p_sni'] = ""
    else:
        await update.message.reply_text("اكتب الـ SNI:"); return SNI_INPUT
    return await ask_final(update, context)

async def get_sni_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_sni'] = update.message.text
    return await ask_final(update, context)

async def ask_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("9️⃣ السعر بالنقاط:")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text)
        products = load_json(FILES['prods'])
        pid = str(uuid.uuid4())[:8]
        products[pid] = {
            "name": context.user_data['p_name'],
            "proto": context.user_data['p_proto'],
            "port": context.user_data['p_port'],
            "addr": context.user_data['p_addr'],
            "uuid": context.user_data['p_uuid'],
            "path": context.user_data['p_path'],
            "host": context.user_data['p_host'],
            "sni": context.user_data['p_sni'],
            "price": price
        }
        save_json(FILES['prods'], products)
        await update.message.reply_text("✅ تم حفظ المنتج بنجاح!", reply_markup=ReplyKeyboardMarkup([["🛒 المنتجات"]], resize_keyboard=True))
        return ConversationHandler.END
    except:
        await update.message.reply_text("❌ أرقام فقط!")
        return PRICE

# --- نظام الشراء وتوليد الروابط ---
async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_json(FILES['prods'])
    if not products:
        await update.message.reply_text("لا يوجد منتجات حالياً.")
        return
    for pid, p in products.items():
        txt = f"📦 {p['name']}\n🚀 {p['proto'].upper()} | 🔌 Port: {p['port']}\n💰 السعر: {p['price']} نقطة"
        kb = [[InlineKeyboardButton("🛒 شراء الآن", callback_data=f"buy_{pid}")]]
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split("_")[1]
    products = load_json(FILES['prods'])
    p = products.get(pid)
    uid = str(query.from_user.id)
    users = load_json(FILES['users'])
    
    if users.get(uid, {}).get("points", 0) < p['price']:
        await query.answer("❌ رصيدك غير كافٍ!", show_alert=True)
        return

    await query.answer("⏳ جاري إنشاء الكود...")
    
    # تفاصيل العميل
    final_uuid = str(uuid.uuid4()) if p['uuid'] == "RANDOM" else p['uuid']
    final_addr = subprocess.getoutput("curl -s ifconfig.me") if p['addr'] == "AUTO" else p['addr']
    email = f"user_{random.randint(100,999)}_{uid}"
    
    # تعديل Xray Config
    config = load_json(FILES['xray'])
    for ib in config['inbounds']:
        if str(ib['port']) == str(p['port']) and ib['protocol'] == p['proto']:
            # إضافة المستخدم للداخل
            if p['proto'] == "shadowsocks":
                ib['settings']['users'].append({"password": final_uuid, "email": email})
            else:
                key = "password" if p['proto'] == "trojan" else "id"
                ib['settings']['clients'].append({key: final_uuid, "email": email})
            
            # تحديث الـ Path الخاص بهذا الانباوند ليكون متوافقاً (ملاحظة: ليدعم تعدد المسارات نحتاج Nginx، لكن هنا نستخدم مسار المنتج)
            ib['streamSettings']['wsSettings']['path'] = p['path']
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
        link = f"vless://{final_uuid}@{final_addr}:{p['port']}?type=ws&security=none&path={p['path']}&host={p['host']}&sni={p['sni']}#{name}"
    elif p['proto'] == "vmess":
        v_j = {"v":"2","ps":name,"add":final_addr,"port":p['port'],"id":final_uuid,"aid":"0","scy":"auto","net":"ws","type":"none","host":p['host'],"path":p['path'],"tls":""}
        link = "vmess://" + subprocess.getoutput(f"echo '{json.dumps(v_j)}' | base64 -w 0")
    elif p['proto'] == "trojan":
        link = f"trojan://{final_uuid}@{final_addr}:{p['port']}?type=ws&security=none&path={p['path']}&host={p['host']}#{name}"
    elif p['proto'] == "shadowsocks":
        ss_b = subprocess.getoutput(f"echo -n 'chacha20-ietf-poly1305:{final_uuid}' | base64 -w 0")
        link = f"ss://{ss_b}@{final_addr}:{p['port']}?type=ws&path={p['path']}&host={p['host']}#{name}"

    await query.message.reply_text(f"✅ تم الشراء بنجاح!\n\n`{link}`", parse_mode='Markdown')

# --- تشغيل البوت ---
def main():
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة منتج"), add_prod_start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PROTOCOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_proto)],
            PORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_port)],
            ADDRESS_CHOICE: [MessageHandler(filters.TEXT, get_addr_choice)],
            ADDRESS_INPUT: [MessageHandler(filters.TEXT, get_addr_input)],
            UUID_CHOICE: [MessageHandler(filters.TEXT, get_uuid_choice)],
            UUID_INPUT: [MessageHandler(filters.TEXT, get_uuid_input)],
            PATH_CHOICE: [MessageHandler(filters.TEXT, get_path_choice)],
            PATH_INPUT: [MessageHandler(filters.TEXT, get_path_input)],
            HOST_CHOICE: [MessageHandler(filters.TEXT, get_host_choice)],
            HOST_INPUT: [MessageHandler(filters.TEXT, get_host_input)],
            SNI_CHOICE: [MessageHandler(filters.TEXT, get_sni_choice)],
            SNI_INPUT: [MessageHandler(filters.TEXT, get_sni_input)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
        },
        fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^🛒 المنتجات|^🛍️ المتجر"), show_products))
    app.add_handler(CallbackQueryHandler(buy_callback, pattern="^buy_"))
    
    print("🚀 البوت المطور يعمل الآن...")
    app.run_polling()

if __name__ == '__main__':
    main()
