import os, subprocess, json, sys, time, uuid, random, string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except: sys.exit("❌ Config missing")

FILES = {"prods": "/etc/my-v2ray/products.json", "users": "/etc/my-v2ray/users.json", "xray": "/usr/local/etc/xray/config.json"}

# مراحل المحادثة
(NAME, DESC, MEDIA, PROTOCOL, PORT, ADDRESS_CHOICE, ADDRESS_INPUT, UUID_CHOICE, UUID_INPUT, PATH_CHOICE, PATH_INPUT, HOST_CHOICE, HOST_INPUT, SNI_CHOICE, SNI_INPUT, PRICE) = range(16)

def load_json(p):
    try:
        with open(p, 'r') as f: return json.load(f)
    except: return {}

def save_json(p, d):
    with open(p, 'w') as f: json.dump(d, f, indent=4)

def restart_xray():
    os.system("systemctl restart xray")

# --- لوحة مراقبة السيرفر (لأدمن) ---
def get_server_stats():
    try:
        # فحص الاتصالات الحالية عبر نظام Linux
        cmd = "netstat -anp | grep ESTABLISHED | grep xray | wc -l"
        total_conns = subprocess.getoutput(cmd)
        
        # فحص البورتات المفتوحة
        config = load_json(FILES['xray'])
        stats_text = "📊 **لوحة مراقبة السيرفر**\n\n"
        stats_text += f"👥 إجمالي الاتصالات الحالية: `{total_conns}`\n"
        stats_text += "------------------------\n"
        
        for ib in config.get('inbounds', []):
            if ib.get('port') == 10085: continue
            port = ib.get('port')
            proto = ib.get('protocol')
            # حساب عدد المستخدمين المسجلين في هذا البورت
            if proto == "shadowsocks":
                count = len(ib.get('settings', {}).get('users', []))
            else:
                count = len(ib.get('settings', {}).get('clients', []))
            
            stats_text += f"🔌 Port: `{port}` | 🛡️ `{proto}` | 👥 `{count}` مستخدم\n"
        
        return stats_text
    except Exception as e:
        return f"❌ خطأ في جلب البيانات: {e}"

# --- معالج البورتات الجديد (يدعم التعدد) ---
def ensure_port_config(protocol, port):
    config = load_json(FILES['xray'])
    port = int(port)
    
    # البحث إذا كان البورت موجوداً
    for ib in config['inbounds']:
        if ib.get('port') == port:
            if ib['protocol'] == protocol:
                return True, "✅ البورت مفتوح مسبقاً لهذا البروتوكول."
            else:
                # إذا كان البورت مشغول ببروتوكول آخر، سنسمح بذلك عبر إنشاء Inbound جديد بنفس البورت
                # ملاحظة: Xray يدعم تعدد البروتوكولات على نفس البورت في بعض الحالات، لكن الأفضل فصلهم بـ Tags
                pass

    # إنشاء Inbound جديد
    new_ib = {
        "port": port,
        "protocol": protocol,
        "settings": {"clients": [], "decryption": "none"} if protocol != "shadowsocks" else {"users": [], "method": "chacha20-ietf-poly1305"},
        "streamSettings": {"network": "ws", "wsSettings": {"path": "/"}},
        "tag": f"tag_{port}_{protocol}_{random.randint(100,999)}"
    }
    if protocol == "trojan": new_ib["settings"] = {"clients": []}
    
    config['inbounds'].append(new_ib)
    save_json(FILES['xray'], config)
    restart_xray()
    return True, f"✅ تم تهيئة البورت {port} لبروتوكول {protocol}."

# --- البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == int(ADMIN_ID):
        kb = [["➕ إضافة منتج", "📊 مراقبة السيرفر"], ["🛒 المنتجات", "🔄 ريستارت Xray"]]
        await update.message.reply_text("👋 أهلاً بك يا مدير. اختر من القائمة:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        kb = [["🛍️ المتجر", "💰 رصيدي"]]
        await update.message.reply_text("مرحباً بك في بوت البيع:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- معالج إضافة المنتج (الخطوات اليدوية) ---
async def add_prod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("1️⃣ اسم المنتج (مثلاً: تروجان بورت 80):", reply_markup=ReplyKeyboardMarkup([["🔙 إلغاء"]], resize_keyboard=True))
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_name'] = update.message.text
    await update.message.reply_text("2️⃣ اختر البروتوكول:", reply_markup=ReplyKeyboardMarkup([["vless", "vmess"], ["trojan", "shadowsocks"]], resize_keyboard=True))
    return PROTOCOL

async def get_proto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    await update.message.reply_text("3️⃣ رقم البورت:")
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    port = update.message.text
    proto = context.user_data['p_proto']
    ok, msg = ensure_port_config(proto, port)
    context.user_data['p_port'] = port
    await update.message.reply_text(f"{msg}\n\n4️⃣ العنوان (IP/دومين):", reply_markup=ReplyKeyboardMarkup([["📍 تلقائي IP"], ["✏️ يدوي"]], resize_keyboard=True))
    return ADDRESS_CHOICE

async def get_addr_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "تلقائي" in update.message.text:
        context.user_data['p_addr'] = "AUTO"
        return await ask_uuid(update, context)
    await update.message.reply_text("اكتب العنوان:"); return ADDRESS_INPUT

async def get_addr_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_addr'] = update.message.text
    return await ask_uuid(update, context)

async def ask_uuid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("5️⃣ نظام UUID:", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"], ["✏️ يدوي"]], resize_keyboard=True))
    return UUID_CHOICE

async def get_uuid_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_uuid'] = "RANDOM"
        return await ask_path(update, context)
    await update.message.reply_text("اكتب الـ UUID:"); return UUID_INPUT

async def get_uuid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_uuid'] = update.message.text
    return await ask_path(update, context)

async def ask_path(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("6️⃣ المسار (Path):", reply_markup=ReplyKeyboardMarkup([["🎲 عشوائي"], ["✏️ يدوي"]], resize_keyboard=True))
    return PATH_CHOICE

async def get_path_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_path'] = "/" + "".join(random.choices(string.ascii_lowercase, k=5))
    else:
        await update.message.reply_text("اكتب المسار:"); return PATH_INPUT
    return await ask_host(update, context)

async def get_path_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = update.message.text
    context.user_data['p_path'] = p if p.startswith("/") else "/" + p
    return await ask_host(update, context)

async def ask_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("7️⃣ الـ Host:", reply_markup=ReplyKeyboardMarkup([["❌ فارغ"], ["✏️ يدوي"]], resize_keyboard=True))
    return HOST_CHOICE

async def get_host_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "فارغ" in update.message.text:
        context.user_data['p_host'] = ""
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
    return await ask_price(update, context)

async def get_sni_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "فارغ" in update.message.text: context.user_data['p_sni'] = ""
    else: await update.message.reply_text("اكتب الـ SNI:"); return SNI_INPUT
    return await ask_price(update, context)

async def get_sni_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_sni'] = update.message.text
    return await ask_price(update, context)

async def ask_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("9️⃣ السعر بالنقاط:")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pr = int(update.message.text)
        prods = load_json(FILES['prods'])
        pid = str(uuid.uuid4())[:8]
        prods[pid] = {
            "name": context.user_data['p_name'], "proto": context.user_data['p_proto'],
            "port": context.user_data['p_port'], "addr": context.user_data['p_addr'],
            "uuid": context.user_data['p_uuid'], "path": context.user_data['p_path'],
            "host": context.user_data['p_host'], "sni": context.user_data['p_sni'], "price": pr
        }
        save_json(FILES['prods'], prods)
        await update.message.reply_text("✅ تم الحفظ!", reply_markup=ReplyKeyboardMarkup([["🛒 المنتجات"]], resize_keyboard=True))
        return ConversationHandler.END
    except: return PRICE

# --- إدارة الضغطات والأدمن ---
async def handle_admin_tools(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt == "📊 مراقبة السيرفر":
        stats = get_server_stats()
        await update.message.reply_text(stats, parse_mode='Markdown')
    elif txt == "🔄 ريستارت Xray":
        restart_xray()
        await update.message.reply_text("✅ تم إعادة تشغيل السيرفر.")

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prods = load_json(FILES['prods'])
    if not prods: await update.message.reply_text("المتجر فارغ.")
    for pid, p in prods.items():
        kb = [[InlineKeyboardButton("🛒 شراء", callback_data=f"buy_{pid}")]]
        await update.message.reply_text(f"📦 {p['name']}\n💰 السعر: {p['price']}", reply_markup=InlineKeyboardMarkup(kb))

async def process_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split("_")[1]
    p = load_json(FILES['prods']).get(pid)
    uid = str(query.from_user.id)
    users = load_json(FILES['users'])
    
    if users.get(uid, {}).get("points", 0) < p['price']:
        await query.answer("❌ لا يوجد رصيد", show_alert=True); return

    # توليد الكود والاتصال
    f_uuid = str(uuid.uuid4()) if p['uuid'] == "RANDOM" else p['uuid']
    f_addr = subprocess.getoutput("curl -s ifconfig.me") if p['addr'] == "AUTO" else p['addr']
    
    # تحديث Xray
    config = load_json(FILES['xray'])
    for ib in config['inbounds']:
        if str(ib['port']) == str(p['port']) and ib['protocol'] == p['proto']:
            if p['proto'] == "shadowsocks":
                ib['settings']['users'].append({"password": f_uuid, "email": f"u_{uid}_{random.randint(10,99)}"})
            else:
                key = "password" if p['proto'] == "trojan" else "id"
                ib['settings']['clients'].append({key: f_uuid, "email": f"u_{uid}_{random.randint(10,99)}"})
            ib['streamSettings']['wsSettings']['path'] = p['path']
            break
    
    save_json(FILES['xray'], config)
    restart_xray()
    users[uid]['points'] -= p['price']
    save_json(FILES['users'], users)
    
    # توليد الرابط (نفس التنسيق المصلح سابقاً)
    res = f"✅ كودك جاهز:\n\n"
    if p['proto'] == "vless":
        res += f"`vless://{f_uuid}@{f_addr}:{p['port']}?type=ws&security=none&path={p['path']}&host={p['host']}&sni={p['sni']}#Shop`"
    elif p['proto'] == "trojan":
        res += f"`trojan://{f_uuid}@{f_addr}:{p['port']}?type=ws&security=none&path={p['path']}&host={p['host']}#Shop`"
    # ... (باقي البروتوكولات بنفس الطريقة)
    
    await query.message.reply_text(res, parse_mode='Markdown')

def main():
    app = Application.builder().token(TOKEN).build()
    
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة منتج"), add_prod_start)],
        states={
            NAME: [MessageHandler(filters.TEXT, get_name)],
            PROTOCOL: [MessageHandler(filters.TEXT, get_proto)],
            PORT: [MessageHandler(filters.TEXT, get_port)],
            ADDRESS_CHOICE: [MessageHandler(filters.TEXT, get_address_choice)],
            ADDRESS_INPUT: [MessageHandler(filters.TEXT, get_address_input)],
            UUID_CHOICE: [MessageHandler(filters.TEXT, get_uuid_choice)],
            UUID_INPUT: [MessageHandler(filters.TEXT, get_uuid_input)],
            PATH_CHOICE: [MessageHandler(filters.TEXT, get_path_choice)],
            PATH_INPUT: [MessageHandler(filters.TEXT, get_path_input)],
            HOST_CHOICE: [MessageHandler(filters.TEXT, get_host_choice)],
            HOST_INPUT: [MessageHandler(filters.TEXT, get_host_input)],
            SNI_CHOICE: [MessageHandler(filters.TEXT, get_sni_choice)],
            SNI_INPUT: [MessageHandler(filters.TEXT, get_sni_input)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
        }, fallbacks=[CommandHandler("cancel", lambda u,c: ConversationHandler.END)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^📊 مراقبة|^🔄 ريستارت"), handle_admin_tools))
    app.add_handler(MessageHandler(filters.Regex("^🛒 المنتجات|^🛍️ المتجر"), show_shop))
    app.add_handler(CallbackQueryHandler(process_buy, pattern="^buy_"))
    
    app.run_polling()

if __name__ == '__main__': main()
