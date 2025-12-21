import os, subprocess, json, sys, time, uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except: sys.exit("Config missing")

FILES = {"prods": "/etc/my-v2ray/products.json", "users": "/etc/my-v2ray/users.json", "xray": "/usr/local/etc/xray/config.json"}

# مراحل المحادثة
(NAME, DESC, MEDIA, PROTOCOL, PORT, LIMIT, QUOTA, DURATION, PRICE, ADMIN_USER_ID, ADMIN_POINTS) = range(11)

# --- دوال النظام ---
def load_json(path):
    if not os.path.exists(path): return {}
    with open(path, 'r') as f: return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=4)

def restart_xray():
    os.system("systemctl restart xray")

# دالة ذكية لإضافة أو تحديث الـ Inbound في Xray
def ensure_inbound(protocol, port):
    config = load_json(FILES['xray'])
    port = int(port)
    
    # هل البورت موجود مسبقاً؟
    for inbound in config['inbounds']:
        if inbound.get('port') == port:
            if inbound['protocol'] != protocol:
                return False # خطأ: البورت مشغول ببروتوكول آخر
            return True # البورت موجود وجاهز
            
    # إذا لم يكن موجوداً، قم بإنشائه
    new_inbound = {
        "port": port,
        "protocol": protocol,
        "settings": {
            "clients": [] if protocol != "shadowsocks" else [],
            "users": [] if protocol == "shadowsocks" else [], # الشادوسوكس يستخدم users
            "decryption": "none"
        },
        "streamSettings": {
            "network": "ws",
            "wsSettings": {"path": "/"} # مسار افتراضي يمكن تعديله
        }
    }
    
    # تعديلات خاصة لكل بروتوكول
    if protocol == "shadowsocks":
        new_inbound["settings"] = {
            "method": "chacha20-ietf-poly1305", # تشفير قوي وحديث
            "users": [],
            "network": "tcp,udp"
        }
        del new_inbound["streamSettings"] # الشادوسوكس غالباً TCP صافي
    elif protocol == "trojan":
        # تروجان يحتاج شهادة، سنجعله يعمل بدون TLS للتبسيط أو يحتاج إعدادات إضافية
        # سنستخدم Fallback بسيط هنا لغرض البوت
        pass 

    config['inbounds'].append(new_inbound)
    save_json(FILES['xray'], config)
    return True

# --- البداية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == int(ADMIN_ID):
        kb = [["🛒 المنتجات", "👥 إدارة المستخدمين"], ["➕ منتج جديد", "⚙️ تحديث السيرفر"]]
        await update.message.reply_text("👮‍♂️ لوحة تحكم الأدمن الشاملة:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        kb = [["🛍️ شراء كود", "💰 رصيدي"], ["🆘 الدعم"]]
        await update.message.reply_text("👋 أهلاً بك في متجر الخدمات السريعة!", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- إضافة منتج (Wizard) ---
async def add_prod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("1️⃣ اسم المنتج (الزر):", reply_markup=ReplyKeyboardMarkup([["🔙 إلغاء"]], resize_keyboard=True))
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 إلغاء": return ConversationHandler.END
    context.user_data['p_name'] = update.message.text
    await update.message.reply_text("2️⃣ الوصف:")
    return DESC

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_desc'] = update.message.text
    await update.message.reply_text("3️⃣ صورة/فيديو (أو اكتب 'تخطي'):")
    return MEDIA

async def get_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['media'] = update.message.photo[-1].file_id if update.message.photo else None
    kb = [["vless", "vmess"], ["trojan", "shadowsocks"]]
    await update.message.reply_text("4️⃣ اختر البروتوكول:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return PROTOCOL

async def get_protocol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    await update.message.reply_text("5️⃣ اكتب رقم البورت (مثال: 80, 443, 2053, 8080):")
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    port = update.message.text
    if not port.isdigit():
        await update.message.reply_text("❌ يجب أن يكون رقماً.")
        return PORT
    
    # محاولة تجهيز البورت في السيرفر
    proto = context.user_data['p_proto']
    if ensure_inbound(proto, port):
        context.user_data['p_port'] = port
        await update.message.reply_text("6️⃣ عدد الأجهزة المسموحة:")
        return LIMIT
    else:
        await update.message.reply_text(f"❌ البورت {port} مشغول ببروتوكول آخر! اختر بورت غيره.")
        return PORT

async def get_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_limit'] = update.message.text
    await update.message.reply_text("7️⃣ السعة (مثال: 50G):")
    return QUOTA

async def get_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_quota'] = update.message.text
    await update.message.reply_text("8️⃣ المدة (مثال: 30d):")
    return DURATION

async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_time'] = update.message.text
    await update.message.reply_text("9️⃣ السعر (نقاط):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = int(update.message.text)
    data = context.user_data
    products = load_json(FILES['prods'])
    pid = str(uuid.uuid4())[:6]
    
    products[pid] = {
        "name": data['p_name'], "desc": data['p_desc'], "media": data['media'],
        "proto": data['p_proto'], "port": data['p_port'], "limit": data['p_limit'],
        "quota": data['p_quota'], "time": data['p_time'], "price": price
    }
    save_json(FILES['prods'], products)
    restart_xray()
    await update.message.reply_text("✅ تم إضافة المنتج وتجهيز البورت في السيرفر!", reply_markup=ReplyKeyboardMarkup([["🛒 المنتجات"]], resize_keyboard=True))
    return ConversationHandler.END

# --- الشراء والتوليد ---
async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_json(FILES['prods'])
    kb = []
    for pid, p in products.items():
        kb.append([InlineKeyboardButton(f"{p['name']} | {p['price']}💰", callback_data=f"buy_{pid}")])
    
    if not kb: await update.message.reply_text("المتجر فارغ حالياً.")
    else: await update.message.reply_text("اختر الباقة:", reply_markup=InlineKeyboardMarkup(kb))

async def process_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split("_")[1]
    products = load_json(FILES['prods'])
    prod = products.get(pid)
    
    # التحقق من الرصيد
    uid = str(query.from_user.id)
    users = load_json(FILES['users'])
    points = users.get(uid, {}).get("points", 0)
    
    if points < prod['price']:
        await query.answer("❌ رصيدك لا يكفي!", show_alert=True)
        return
    
    await query.answer("جاري التجهيز...")
    
    # تجهيز القيم
    try:
        # تحويل السعة والوقت
        q_str = prod['quota'].upper()
        size = int(''.join(filter(str.isdigit, q_str)))
        max_bytes = size * 1024**3 if "G" in q_str else size * 1024**2
        
        t_str = prod['time'].lower()
        t_val = int(''.join(filter(str.isdigit, t_str)))
        exp_time = int(time.time()) + (t_val * 86400 if "d" in t_str else t_val * 3600)
        
        # إنشاء User في Xray
        config = load_json(FILES['xray'])
        target_inbound = None
        for ib in config['inbounds']:
            if ib.get('port') == int(prod['port']) and ib['protocol'] == prod['proto']:
                target_inbound = ib
                break
        
        if not target_inbound:
            await query.message.reply_text("❌ خطأ: البورت غير موجود في السيرفر.")
            return

        user_uuid = str(uuid.uuid4())
        email = f"limit_{prod['limit']}_max_{max_bytes}_exp_{exp_time}_{user_uuid[:5]}"
        ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()

        # إضافة حسب البروتوكول
        if prod['proto'] == "shadowsocks":
            # في شادوسوكس نستخدم password بدلاً من id
            client_entry = {"password": user_uuid, "email": email}
            if 'users' not in target_inbound['settings']: target_inbound['settings']['users'] = []
            target_inbound['settings']['users'].append(client_entry)
            link = f"ss://{subprocess.getoutput('echo -n chacha20-ietf-poly1305:'+user_uuid+' | base64')}@{ip}:{prod['port']}#{prod['name']}"
        
        else: # vless, vmess, trojan
            client_entry = {"id": user_uuid, "email": email}
            target_inbound['settings']['clients'].append(client_entry)
            
            type_q = "ws" if target_inbound.get("streamSettings", {}).get("network") == "ws" else "tcp"
            if prod['proto'] == "vless":
                link = f"vless://{user_uuid}@{ip}:{prod['port']}?type={type_q}&path=/&security=none#{prod['name']}"
            elif prod['proto'] == "vmess":
                # رابط VMess يحتاج JSON وتشفير Base64 (تبسيط للكود)
                vmess_json = {"v": "2","ps": prod['name'],"add": ip,"port": prod['port'],"id": user_uuid,"aid": "0","net": type_q,"type": "none","host": "","path": "/","tls": ""}
                link = "vmess://" + subprocess.getoutput(f"echo '{json.dumps(vmess_json)}' | base64 -w 0")
            elif prod['proto'] == "trojan":
                link = f"trojan://{user_uuid}@{ip}:{prod['port']}#{prod['name']}"

        save_json(FILES['xray'], config)
        restart_xray()
        
        # خصم النقاط
        if uid not in users: users[uid] = {"points": 0}
        users[uid]["points"] -= prod['price']
        save_json(FILES['users'], users)
        
        await query.message.reply_text(f"✅ تم!\nالرصيد المتبقي: {users[uid]['points']}\n\n`{link}`", parse_mode='Markdown')

    except Exception as e:
        await query.message.reply_text(f"خطأ: {e}")

# --- إدارة المستخدمين (إضافة نقاط) ---
async def manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("👤 أرسل ID المستخدم الذي تريد تعديل نقاطه:")
    return ADMIN_USER_ID

async def get_admin_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['target_uid'] = update.message.text
    await update.message.reply_text("💰 كم النقاط التي تريد إضافتها؟ (اكتب رقم سالب للخصم):")
    return ADMIN_POINTS

async def get_admin_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    points = int(update.message.text)
    uid = context.user_data['target_uid']
    users = load_json(FILES['users'])
    
    if uid not in users: users[uid] = {"points": 0}
    users[uid]["points"] += points
    save_json(FILES['users'], users)
    
    await update.message.reply_text(f"✅ تم تحديث رصيد {uid}. الرصيد الحالي: {users[uid]['points']}")
    return ConversationHandler.END

# --- التشغيل ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    # معالجات المحادثة
    prod_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ منتج جديد"), add_prod_start)],
        states={
            NAME: [MessageHandler(filters.TEXT, get_name)],
            DESC: [MessageHandler(filters.TEXT, get_desc)],
            MEDIA: [MessageHandler(filters.ALL, get_media)],
            PROTOCOL: [MessageHandler(filters.TEXT, get_protocol)],
            PORT: [MessageHandler(filters.TEXT, get_port)],
            LIMIT: [MessageHandler(filters.TEXT, get_limit)],
            QUOTA: [MessageHandler(filters.TEXT, get_quota)],
            DURATION: [MessageHandler(filters.TEXT, get_duration)],
            PRICE: [MessageHandler(filters.TEXT, get_price)],
        }, fallbacks=[]
    )
    
    points_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👥 إدارة المستخدمين"), manage_users)],
        states={
            ADMIN_USER_ID: [MessageHandler(filters.TEXT, get_admin_uid)],
            ADMIN_POINTS: [MessageHandler(filters.TEXT, get_admin_points)]
        }, fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(prod_handler)
    app.add_handler(points_handler)
    app.add_handler(MessageHandler(filters.Regex("^🛒 المنتجات|🛍️ شراء كود"), show_shop))
    app.add_handler(CallbackQueryHandler(process_buy, pattern="^buy_"))
    
    print("✅ البوت الشامل يعمل...")
    app.run_polling()
