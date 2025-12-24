import os, subprocess, json, sys, time, uuid, random, string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except: sys.exit("Config missing")

FILES = {"prods": "/etc/my-v2ray/products.json", "users": "/etc/my-v2ray/users.json", "xray": "/usr/local/etc/xray/config.json"}

# مراحل المحادثة
(NAME, DESC, MEDIA, PROTOCOL, PORT, ADDRESS_CHOICE, ADDRESS_INPUT, UUID_CHOICE, UUID_INPUT, PATH_CHOICE, PATH_INPUT, HOST_CHOICE, HOST_INPUT, SNI_CHOICE, SNI_INPUT, LIMIT, QUOTA, DURATION, PRICE, ADMIN_USER, ADMIN_POINTS) = range(21)

# --- دوال مساعدة ---
def load_json(path):
    if not os.path.exists(path): return {}
    with open(path, 'r') as f: return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

def restart_xray():
    os.system("systemctl restart xray")

def random_path(length=6):
    return "/" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

# --- التعامل مع Xray ---
def ensure_inbound(protocol, port):
    """
    هذه الدالة تتأكد فقط من أن البورت مفتوح.
    إذا كان مفتوحاً مسبقاً بنفس البروتوكول، تسمح باستخدامه (ميزة تعدد المنتجات).
    """
    config = load_json(FILES['xray'])
    port = int(port)
    
    # التحقق هل البورت موجود
    for ib in config['inbounds']:
        if ib.get('port') == port:
            # البورت موجود.. هل هو نفس البروتوكول؟
            if ib['protocol'] == protocol:
                return True, "✅ البورت مفتوح مسبقاً بنفس البروتوكول، سيتم إضافة المنتج عليه."
            else:
                return False, f"❌ خطأ: البورت {port} مشغول ببروتوكول آخر ({ib['protocol']})."

    # إذا البورت غير موجود، نقوم بإنشائه بوضع Websocket افتراضي
    stream_settings = {
        "network": "ws",
        "wsSettings": { "path": "/" } # المسار سيتغير لكل مستخدم لاحقاً أو يتم تجاهله هنا
    }
    
    settings = {}
    if protocol == "shadowsocks":
        settings = {
            "method": "chacha20-ietf-poly1305",
            "users": [],
            "network": "tcp,udp"
        }
    elif protocol in ["vless", "vmess", "trojan"]:
        settings = {"clients": [], "decryption": "none"}

    new_inbound = {
        "port": port,
        "protocol": protocol,
        "settings": settings,
        "streamSettings": stream_settings,
        "tag": f"tag_{port}_{protocol}" # تاج مميز
    }
    
    config['inbounds'].append(new_inbound)
    save_json(FILES['xray'], config)
    return True, "✅ تم فتح بورت جديد في السيرفر."

# --- البداية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == int(ADMIN_ID):
        kb = [["🛒 المنتجات", "👥 إدارة المستخدمين"], ["➕ منتج جديد", "⚙️ تحديث السيرفر"]]
        await update.message.reply_text("👮‍♂️ لوحة التحكم:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        kb = [["🛍️ شراء كود", "💰 رصيدي"], ["🆘 دعم فني"]]
        await update.message.reply_text("👋 أهلاً بك في المتجر:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- إضافة منتج ---
async def add_prod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return ConversationHandler.END
    await update.message.reply_text("1️⃣ اسم المنتج:", reply_markup=ReplyKeyboardMarkup([["🔙 إلغاء"]], resize_keyboard=True))
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 إلغاء": return ConversationHandler.END
    context.user_data['p_name'] = update.message.text
    await update.message.reply_text("2️⃣ الوصف:")
    return DESC

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_desc'] = update.message.text
    await update.message.reply_text("3️⃣ ميديا (صورة/فيديو) أو 'تخطي':")
    return MEDIA

async def get_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['media'] = update.message.photo[-1].file_id if update.message.photo else None
    if update.message.video: context.user_data['media'] = update.message.video.file_id
    
    kb = [["vless", "vmess"], ["trojan", "shadowsocks"]]
    await update.message.reply_text("4️⃣ اختر البروتوكول (الكل WS):", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return PROTOCOL

async def get_protocol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    await update.message.reply_text("5️⃣ رقم البورت (يمكن تكراره لنفس البروتوكول):")
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.isdigit(): return PORT
    port = update.message.text
    proto = context.user_data['p_proto']
    
    # التحقق من إمكانية استخدام البورت
    ok, msg = ensure_inbound(proto, port)
    if not ok:
        await update.message.reply_text(msg)
        return PORT # إعادة السؤال
        
    context.user_data['p_port'] = port
    await update.message.reply_text(f"{msg}\n\n6️⃣ عنوان الاتصال (IP/Domain):", 
                                    reply_markup=ReplyKeyboardMarkup([["📍 تلقائي"], ["✏️ يدوي"]], resize_keyboard=True))
    return ADDRESS_CHOICE

async def get_address_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "تلقائي" in update.message.text:
        context.user_data['p_addr'] = "AUTO"
        return await ask_uuid(update, context)
    else:
        await update.message.reply_text("اكتب الدومين/IP:")
        return ADDRESS_INPUT

async def get_address_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_addr'] = update.message.text
    return await ask_uuid(update, context)

async def ask_uuid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["🎲 عشوائي (لكل زبون كود مختلف)"], ["✏️ يدوي (كود ثابت للجميع)"]]
    await update.message.reply_text("7️⃣ نظام UUID/Password:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return UUID_CHOICE

async def get_uuid_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_uuid'] = "RANDOM"
        return await ask_path(update, context)
    else:
        await update.message.reply_text("اكتب الكود/الباسورد الثابت:")
        return UUID_INPUT

async def get_uuid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_uuid'] = update.message.text
    return await ask_path(update, context)

async def ask_path(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["🎲 مسار عشوائي"], ["✏️ مسار يدوي"]]
    await update.message.reply_text("8️⃣ المسار (Path):", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return PATH_CHOICE

async def get_path_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_path'] = random_path()
        return await ask_host(update, context)
    else:
        await update.message.reply_text("اكتب المسار (مثال /speed):")
        return PATH_INPUT

async def get_path_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_path'] = update.message.text
    return await ask_host(update, context)

async def ask_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["❌ فارغ"], ["✏️ كتابة Host"]]
    await update.message.reply_text("9️⃣ إعدادات Host:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return HOST_CHOICE

async def get_host_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "فارغ" in update.message.text:
        context.user_data['p_host'] = ""
        return await ask_sni(update, context)
    else:
        await update.message.reply_text("اكتب Host:")
        return HOST_INPUT

async def get_host_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_host'] = update.message.text
    return await ask_sni(update, context)

async def ask_sni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data['p_port'] == "443":
        kb = [["❌ فارغ"], ["✏️ كتابة SNI"]]
        await update.message.reply_text("🔟 إعدادات SNI (لأن البورت 443):", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return SNI_CHOICE
    else:
        context.user_data['p_sni'] = ""
        return await ask_limit(update, context)

async def get_sni_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "فارغ" in update.message.text:
        context.user_data['p_sni'] = ""
        return await ask_limit(update, context)
    else:
        await update.message.reply_text("اكتب SNI:")
        return SNI_INPUT

async def get_sni_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_sni'] = update.message.text
    return await ask_limit(update, context)

async def ask_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1️⃣1️⃣ عدد الأجهزة:")
    return LIMIT

async def get_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_limit'] = update.message.text
    await update.message.reply_text("1️⃣2️⃣ السعة (مثال 10G):")
    return QUOTA

async def get_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_quota'] = update.message.text
    await update.message.reply_text("1️⃣3️⃣ المدة (مثال 30d):")
    return DURATION

async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_time'] = update.message.text
    await update.message.reply_text("1️⃣4️⃣ السعر (نقاط):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = int(update.message.text)
    data = context.user_data
    products = load_json(FILES['prods'])
    pid = str(uuid.uuid4())[:6]
    
    products[pid] = {
        "name": data['p_name'], "desc": data['p_desc'], "media": data['media'],
        "proto": data['p_proto'], "port": data['p_port'], 
        "addr": data['p_addr'], "uuid_mode": data['p_uuid'],
        "path": data['p_path'], "host": data['p_host'], "sni": data.get('p_sni', ''),
        "limit": data['p_limit'], "quota": data['p_quota'], "time": data['p_time'], 
        "price": price
    }
    save_json(FILES['prods'], products)
    
    # ملاحظة: لا نحتاج لعمل ريستارت هنا لأننا لم نعدل الكونفق، فقط حفظنا المنتج
    # سيتم التعديل الحقيقي عند الشراء أو إذا أنشأنا بورت جديد في ensure_inbound
    if "مفتوح مسبقاً" not in ensure_inbound(data['p_proto'], data['p_port'])[1]:
        restart_xray()

    await update.message.reply_text("✅ تم الحفظ!", reply_markup=ReplyKeyboardMarkup([["🛒 المنتجات"]], resize_keyboard=True))
    return ConversationHandler.END

# --- عملية الشراء (إصلاحات هامة هنا) ---
async def process_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split("_")[1]
    products = load_json(FILES['prods'])
    prod = products.get(pid)
    uid = str(query.from_user.id)
    users = load_json(FILES['users'])
    
    # 1. فحص الرصيد
    if users.get(uid, {}).get("points", 0) < prod['price']:
        await query.answer("❌ رصيدك لا يكفي!", show_alert=True)
        return
    
    await query.answer("⏳ جاري التجهيز...")
    try:
        # 2. حساب القيم
        q_str = prod['quota'].upper()
        size = int(''.join(filter(str.isdigit, q_str)))
        max_b = size * (1024**3 if "G" in q_str else 1024**2)
        
        t_str = prod['time'].lower()
        t_val = int(''.join(filter(str.isdigit, t_str)))
        exp_t = int(time.time()) + (t_val * 86400 if "d" in t_str else t_val * 3600)
        
        # 3. تجهيز UUID/Password
        user_uuid = prod['uuid_mode'] if prod['uuid_mode'] != "RANDOM" else str(uuid.uuid4())
        email = f"limit_{prod['limit']}_max_{max_b}_exp_{exp_t}_{user_uuid[:5]}"
        
        # 4. التعديل على ملف Config (إضافة المستخدم)
        config = load_json(FILES['xray'])
        target_inbound = None
        
        # البحث عن البورت الصحيح
        for inbound in config['inbounds']:
            if str(inbound.get('port')) == str(prod['port']) and inbound['protocol'] == prod['proto']:
                target_inbound = inbound
                break
        
        if not target_inbound:
            await query.message.reply_text("❌ خطأ فادح: البورت غير موجود في إعدادات السيرفر.")
            return

        # إضافة العميل حسب البروتوكول
        if prod['proto'] == "shadowsocks":
            if 'users' not in target_inbound['settings']: target_inbound['settings']['users'] = []
            
            # منع التكرار إذا كان UUID ثابت
            exists = any(u['password'] == user_uuid for u in target_inbound['settings']['users'])
            if not exists:
                target_inbound['settings']['users'].append({"password": user_uuid, "email": email, "method": "chacha20-ietf-poly1305"})

        else: # vless, vmess, trojan
            if 'clients' not in target_inbound['settings']: target_inbound['settings']['clients'] = []
            
            exists = any(c.get('id') == user_uuid or c.get('password') == user_uuid for c in target_inbound['settings']['clients'])
            if not exists:
                key = "password" if prod['proto'] == "trojan" else "id"
                target_inbound['settings']['clients'].append({key: user_uuid, "email": email})

        save_json(FILES['xray'], config)
        restart_xray() # مهم جداً لتفعيل المستخدم

        # 5. خصم الرصيد
        if uid not in users: users[uid] = {"points": 0}
        users[uid]["points"] -= prod['price']
        save_json(FILES['users'], users)

        # 6. توليد الرابط
        addr = prod['addr']
        if addr == "AUTO": addr = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
        
        link = ""
        path = prod['path']
        host = prod['host']
        sni = prod['sni']
        
        if prod['proto'] == "vless":
            link = f"vless://{user_uuid}@{addr}:{prod['port']}?type=ws&path={path}&security=none&host={host}&sni={sni}#{prod['name']}"
        
        elif prod['proto'] == "vmess":
            v_json = {
                "v": "2", "ps": prod['name'], "add": addr, "port": prod['port'], "id": user_uuid,
                "aid": "0", "net": "ws", "type": "none", "host": host, "path": path, 
                "tls": "none" if prod['port']!="443" else "tls", "sni": sni
            }
            link = "vmess://" + subprocess.getoutput(f"echo '{json.dumps(v_json)}' | base64 -w 0")
        
        elif prod['proto'] == "trojan":
            # تروجان WS بدون TLS هو الحل الأفضل للتوافق بدون شهادة
            link = f"trojan://{user_uuid}@{addr}:{prod['port']}?type=ws&path={path}&security=none&host={host}#{prod['name']}"
            
        elif prod['proto'] == "shadowsocks":
            # صيغة SS + plugin v2ray-plugin (Standard for WS)
            # SS SIP002 URI Scheme is preferred
            # ss://base64(method:password)@ip:port?plugin=v2ray-plugin%3Bpath%3D%2Fpath%3Bhost%3Dhost
            user_pass = f"chacha20-ietf-poly1305:{user_uuid}"
            user_pass_b64 = subprocess.getoutput(f"echo -n '{user_pass}' | base64 -w 0").strip()
            plugin_opts = f"v2ray-plugin;path={path};host={host}"
            # ترميز الخيارات للرابط
            link = f"ss://{user_pass_b64}@{addr}:{prod['port']}?plugin={plugin_opts}#{prod['name']}"

        await query.message.reply_text(f"✅ تم الشراء بنجاح!\n\n`{link}`", parse_mode='Markdown')

    except Exception as e:
        await query.message.reply_text(f"❌ حدث خطأ: {str(e)}")

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_json(FILES['prods'])
    kb = []
    for pid, p in products.items():
        kb.append([InlineKeyboardButton(f"{p['name']} | {p['price']}💰", callback_data=f"buy_{pid}")])
    if not kb: await update.message.reply_text("المتجر فارغ.")
    else: await update.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup(kb))

# --- هاندلر الإلغاء ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء", reply_markup=ReplyKeyboardMarkup([["🛒 المنتجات"]], resize_keyboard=True))
    return ConversationHandler.END

# --- التشغيل ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ منتج جديد"), add_prod_start)],
        states={
            NAME: [MessageHandler(filters.TEXT, get_name)],
            DESC: [MessageHandler(filters.TEXT, get_desc)],
            MEDIA: [MessageHandler(filters.ALL, get_media)],
            PROTOCOL: [MessageHandler(filters.TEXT, get_protocol)],
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
            LIMIT: [MessageHandler(filters.TEXT, get_limit)],
            QUOTA: [MessageHandler(filters.TEXT, get_quota)],
            DURATION: [MessageHandler(filters.TEXT, get_duration)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
        }, fallbacks=[MessageHandler(filters.Regex("^🔙"), cancel)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^🛒 المنتجات|🛍️"), show_shop))
    app.add_handler(CallbackQueryHandler(process_buy, pattern="^buy_"))
    
    print("✅ البوت يعمل مع الإصلاحات...")
    app.run_polling()
