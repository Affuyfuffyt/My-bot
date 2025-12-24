import os, subprocess, json, sys, time, uuid, random, string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except: sys.exit("Config missing")

FILES = {"prods": "/etc/my-v2ray/products.json", "users": "/etc/my-v2ray/users.json", "xray": "/usr/local/etc/xray/config.json"}

# مراحل المحادثة (تمت إضافة مراحل جديدة)
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

# --- إنشاء Inbound ذكي (WS للكل) ---
def ensure_inbound(protocol, port, path):
    config = load_json(FILES['xray'])
    port = int(port)
    
    # البحث عن البورت
    for ib in config['inbounds']:
        if ib.get('port') == port:
            # إذا البورت موجود، يجب التأكد من تطابق البروتوكول والمسار
            current_path = ib.get('streamSettings', {}).get('wsSettings', {}).get('path', '/')
            if ib['protocol'] != protocol: return False, "❌ البورت مشغول ببروتوكول آخر."
            if current_path != path: return False, f"❌ البورت مشغول بمسار مختلف ({current_path})."
            return True, "✅ تم استخدام البورت الموجود."

    # إعدادات WS الموحدة (تعمل مع SS, Trojan, Vless, Vmess)
    stream = {
        "network": "ws",
        "wsSettings": { "path": path }
    }
    
    settings = {"clients": [], "decryption": "none"}
    
    if protocol == "shadowsocks":
        # في SS نستخدم password وميثود
        settings = {
            "method": "chacha20-ietf-poly1305",
            "users": [],
            "network": "tcp,udp"
        }
    elif protocol == "trojan":
        # تروجان عادة يطلب TLS لكن سنشغله WS صافي (خلف CDN أو مباشر)
        settings = {"clients": []}

    new_inbound = {
        "port": port,
        "protocol": protocol,
        "settings": settings,
        "streamSettings": stream,
        "tag": f"{protocol}_{port}"
    }
    
    config['inbounds'].append(new_inbound)
    save_json(FILES['xray'], config)
    return True, "✅ تم فتح بورت جديد."

# --- البداية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == int(ADMIN_ID):
        kb = [["🛒 المنتجات", "👥 إدارة المستخدمين"], ["➕ منتج جديد", "⚙️ تحديث"]]
        await update.message.reply_text("👮‍♂️ أهلاً بالمدير:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        kb = [["🛍️ شراء كود", "💰 رصيدي"], ["🆘 دعم فني"]]
        await update.message.reply_text("👋 أهلاً بك في المتجر:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- إضافة منتج (الخطوات الجديدة) ---
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
    await update.message.reply_text("3️⃣ ميديا (صورة/فيديو) أو اكتب 'تخطي':")
    return MEDIA

async def get_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['media'] = update.message.photo[-1].file_id if update.message.photo else None
    if update.message.video: context.user_data['media'] = update.message.video.file_id
    
    kb = [["vless", "vmess"], ["trojan", "shadowsocks"]]
    await update.message.reply_text("4️⃣ اختر البروتوكول (الكل سيكون WS):", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return PROTOCOL

async def get_protocol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    await update.message.reply_text("5️⃣ رقم البورت (مثال: 80, 2053, 443):")
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.isdigit(): return PORT
    context.user_data['p_port'] = update.message.text
    
    # --- اختيار العنوان (IP) ---
    kb = [["📍 تلقائي (IP السيرفر)"], ["✏️ يدوي (دومين/CDN)"]]
    await update.message.reply_text("6️⃣ عنوان الاتصال (Address):", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return ADDRESS_CHOICE

async def get_address_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if "تلقائي" in choice:
        context.user_data['p_addr'] = "AUTO"
        # ننتقل للخطوة التالية مباشرة
        return await ask_uuid(update, context)
    else:
        await update.message.reply_text("اكتب العنوان (مثال: my.domain.com):")
        return ADDRESS_INPUT

async def get_address_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_addr'] = update.message.text
    return await ask_uuid(update, context)

async def ask_uuid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["🎲 عشوائي (لكل مشتري)"], ["✏️ يدوي (ثابت للكل)"]]
    await update.message.reply_text("7️⃣ نظام الـ UUID/Password:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return UUID_CHOICE

async def get_uuid_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_uuid'] = "RANDOM"
        return await ask_path(update, context)
    else:
        await update.message.reply_text("اكتب الـ UUID/Password الثابت:")
        return UUID_INPUT

async def get_uuid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_uuid'] = update.message.text
    return await ask_path(update, context)

async def ask_path(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["🎲 مسار عشوائي"], ["✏️ مسار يدوي"]]
    await update.message.reply_text("8️⃣ المسار (Path) للـ WebSocket:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return PATH_CHOICE

async def get_path_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "عشوائي" in update.message.text:
        context.user_data['p_path'] = random_path()
        return await ask_host(update, context)
    else:
        await update.message.reply_text("اكتب المسار (يجب أن يبدأ بـ / مثال: /myspeed):")
        return PATH_INPUT

async def get_path_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    path = update.message.text
    if not path.startswith("/"): path = "/" + path
    context.user_data['p_path'] = path
    return await ask_host(update, context)

async def ask_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # تجهيز البورت في السيرفر الآن لأننا نملك المسار
    proto = context.user_data['p_proto']
    port = context.user_data['p_port']
    path = context.user_data['p_path']
    
    success, msg = ensure_inbound(proto, port, path)
    if not success:
        await update.message.reply_text(msg + "\nأعد المحاولة بمسار أو بورت مختلف.", reply_markup=ReplyKeyboardMarkup([["🔙 إلغاء"]]))
        return ConversationHandler.END
    
    kb = [["❌ بدون Host"], ["✏️ كتابة Host"]]
    await update.message.reply_text(f"{msg}\n9️⃣ إعدادات الـ Host:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return HOST_CHOICE

async def get_host_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "بدون" in update.message.text:
        context.user_data['p_host'] = ""
        return await ask_sni(update, context)
    else:
        await update.message.reply_text("اكتب الـ Host:")
        return HOST_INPUT

async def get_host_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_host'] = update.message.text
    return await ask_sni(update, context)

async def ask_sni(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # الـ SNI يظهر فقط لبورت 443
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
        await update.message.reply_text("اكتب الـ SNI:")
        return SNI_INPUT

async def get_sni_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_sni'] = update.message.text
    return await ask_limit(update, context)

async def ask_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1️⃣1️⃣ عدد الأجهزة المسموحة:")
    return LIMIT

async def get_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_limit'] = update.message.text
    await update.message.reply_text("1️⃣2️⃣ السعة (مثال 50G):")
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
    
    # حفظ المنتج بكامل تفاصيله الجديدة
    products[pid] = {
        "name": data['p_name'], "desc": data['p_desc'], "media": data['media'],
        "proto": data['p_proto'], "port": data['p_port'], 
        "addr": data['p_addr'], "uuid_mode": data['p_uuid'],
        "path": data['p_path'], "host": data['p_host'], "sni": data.get('p_sni', ''),
        "limit": data['p_limit'], "quota": data['p_quota'], "time": data['p_time'], 
        "price": price
    }
    save_json(FILES['prods'], products)
    restart_xray() # لتفعيل البورت والمسار
    
    await update.message.reply_text("✅ تم إضافة المنتج المتطور!", reply_markup=ReplyKeyboardMarkup([["🛒 المنتجات"]], resize_keyboard=True))
    return ConversationHandler.END

# --- الشراء ---
async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_json(FILES['prods'])
    kb = []
    for pid, p in products.items():
        kb.append([InlineKeyboardButton(f"{p['name']} | {p['price']}💰", callback_data=f"buy_{pid}")])
    if not kb: await update.message.reply_text("فارغ.")
    else: await update.message.reply_text("اختر:", reply_markup=InlineKeyboardMarkup(kb))

async def process_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split("_")[1]
    products = load_json(FILES['prods'])
    prod = products.get(pid)
    uid = str(query.from_user.id)
    users = load_json(FILES['users'])
    
    if users.get(uid, {}).get("points", 0) < prod['price']:
        await query.answer("❌ رصيدك لا يكفي!", show_alert=True); return
    
    await query.answer("جاري التجهيز...")
    try:
        # حساب السعة والوقت
        q_str = prod['quota'].upper()
        size = int(''.join(filter(str.isdigit, q_str)))
        max_b = size * (1024**3 if "G" in q_str else 1024**2)
        
        t_str = prod['time'].lower()
        t_val = int(''.join(filter(str.isdigit, t_str)))
        exp_t = int(time.time()) + (t_val * 86400 if "d" in t_str else t_val * 3600)
        
        # تحديد الـ UUID/Password
        if prod['uuid_mode'] == "RANDOM":
            user_id = str(uuid.uuid4())
        else:
            user_id = prod['uuid_mode'] # يدوي ثابت
            
        email = f"limit_{prod['limit']}_max_{max_b}_exp_{exp_t}_{user_id[:5]}"
        
        # تحديد العنوان IP
        address = prod['addr']
        if address == "AUTO":
            address = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
            
        # إضافة للسيرفر
        config = load_json(FILES['xray'])
        target_ib = None
        for ib in config['inbounds']:
            if str(ib['port']) == str(prod['port']) and ib['protocol'] == prod['proto']:
                target_ib = ib; break
        
        if not target_ib: await query.message.reply_text("خطأ: البورت غير موجود"); return

        # بناء الرابط وإضافة المستخدم
        link = ""
        path = prod['path']
        host = prod['host']
        sni = prod['sni']
        
        if prod['proto'] == "shadowsocks":
            # SS + WS
            entry = {"password": user_id, "email": email}
            # منع التكرار إذا كان ثابت
            exists = False
            for u in target_ib['settings'].get('users', []):
                if u['password'] == user_id: exists = True; break
            if not exists: 
                if 'users' not in target_ib['settings']: target_ib['settings']['users'] = []
                target_ib['settings']['users'].append(entry)
            
            # رابط SS بصيغة Xray النظيفة
            # ss://method:pass@ip:port?type=ws&path=/path&host=host#name
            # ملاحظة: SS WS يحتاج ترميز خاص أحياناً، لكن هذه الصيغة تعمل مع معظم العملاء الحديثين
            # سنستخدم صيغة Base64 التقليدية
            base = subprocess.getoutput(f"echo -n 'chacha20-ietf-poly1305:{user_id}' | base64 -w 0")
            link = f"ss://{base}@{address}:{prod['port']}?type=ws&path={path}&host={host}#{prod['name']}"

        else: # VLESS, VMESS, TROJAN
            entry = {"id": user_id, "email": email}
            # منع تكرار ID الثابت
            exists = False
            for c in target_ib['settings'].get('clients', []):
                if c['id'] == user_id: exists = True; break
            if not exists: target_ib['settings']['clients'].append(entry)

            if prod['proto'] == "vless":
                link = f"vless://{user_id}@{address}:{prod['port']}?type=ws&path={path}&security=none&host={host}&sni={sni}#{prod['name']}"
            elif prod['proto'] == "vmess":
                # VMess JSON
                v_json = {
                    "v": "2", "ps": prod['name'], "add": address, "port": prod['port'], "id": user_id,
                    "aid": "0", "net": "ws", "type": "none", "host": host, "path": path, "tls": "none" if prod['port']!="443" else "tls", "sni": sni
                }
                link = "vmess://" + subprocess.getoutput(f"echo '{json.dumps(v_json)}' | base64 -w 0")
            elif prod['proto'] == "trojan":
                # Trojan WS
                link = f"trojan://{user_id}@{address}:{prod['port']}?type=ws&path={path}&security=none&host={host}&sni={sni}#{prod['name']}"

        save_json(FILES['xray'], config)
        restart_xray()
        
        if uid not in users: users[uid] = {"points": 0}
        users[uid]["points"] -= prod['price']
        save_json(FILES['users'], users)
        
        await query.message.reply_text(f"✅ تم الشراء!\n\n`{link}`", parse_mode='Markdown')

    except Exception as e: await query.message.reply_text(f"Error: {e}")

# --- التشغيل ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    # تعريف الهاندلر الطويل
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
        }, fallbacks=[MessageHandler(filters.Regex("^🔙"), lambda u,c: ConversationHandler.END)]
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^🛒 المنتجات|🛍️"), show_shop))
    app.add_handler(CallbackQueryHandler(process_buy, pattern="^buy_"))
    
    print("✅ البوت المتطور يعمل...")
    app.run_polling()
