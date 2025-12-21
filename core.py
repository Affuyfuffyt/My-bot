import os, subprocess, json, sys, time, uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except:
    sys.exit("Config file missing")

# ملفات البيانات
PRODUCTS_FILE = "/etc/my-v2ray/products.json"
USERS_FILE = "/etc/my-v2ray/users.json"

# مراحل المحادثة (إضافة منتج)
(NAME, DESC, MEDIA, PROTOCOL, PORT, LIMIT, QUOTA, DURATION, PRICE) = range(9)

# --- دوال مساعدة ---
def load_data(file):
    if not os.path.exists(file): return {}
    with open(file, 'r') as f: return json.load(f)

def save_data(file, data):
    with open(file, 'w') as f: json.dump(data, f, indent=4)

def get_user_points(user_id):
    users = load_data(USERS_FILE)
    return users.get(str(user_id), {}).get("points", 0)

# --- القوائم الرئيسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # لوحة الأدمن
    if user_id == int(ADMIN_ID):
        keyboard = [["🔑 الحصول على كود"], ["⚙️ الإعدادات"]]
        await update.message.reply_text("أهلاً بك يا مدير 👨‍✈️", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        # لوحة المستخدم
        keyboard = [["🔑 الحصول على كود"], ["💰 رصيدي"]]
        await update.message.reply_text("أهلاً بك في متجر السرعة 🚀", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

# --- قائمة الأدمن ---
async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    keyboard = [["➕ إضافة كودات (منتج جديد)"], ["🔙 رجوع"]]
    await update.message.reply_text("⚙️ إعدادات الإدارة:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

# --- معالج إضافة منتج جديد (Wizard) ---
async def add_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(ADMIN_ID): return
    await update.message.reply_text("📝 أدخل اسم الزر (المنتج) الذي سيظهر للمستخدمين:", reply_markup=ReplyKeyboardMarkup([["🔙 إلغاء"]], resize_keyboard=True))
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔙 إلغاء": return await cancel(update, context)
    context.user_data['p_name'] = update.message.text
    await update.message.reply_text("📝 أدخل وصف المنتج (وصف جذاب):")
    return DESC

async def get_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_desc'] = update.message.text
    await update.message.reply_text("📷 أرسل صورة أو فيديو للمنتج (أو اكتب 'تخطي'):")
    return MEDIA

async def get_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['p_media'] = update.message.photo[-1].file_id
        context.user_data['p_media_type'] = 'photo'
    elif update.message.video:
        context.user_data['p_media'] = update.message.video.file_id
        context.user_data['p_media_type'] = 'video'
    else:
        context.user_data['p_media'] = None
    
    keyboard = [["vless", "vmess"], ["trojan", "shadowsocks"]]
    await update.message.reply_text("📡 اختر البروتوكول:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return PROTOCOL

async def get_protocol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    # حالياً ندعم بورت 80 فقط حسب التثبيت، لكن نترك الخيار للمستقبل
    keyboard = [["80 (Websocket)"], ["443 (TLS) - يحتاج شهادة"]]
    await update.message.reply_text("🔌 اختر البوت/البورت:", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))
    return PORT

async def get_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_port'] = "80" if "80" in update.message.text else "443"
    await update.message.reply_text("📱 كم عدد الأجهزة المسموح؟ (أرسل رقم فقط)")
    return LIMIT

async def get_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_limit'] = update.message.text
    await update.message.reply_text("💾 كم سعة البيانات؟ (مثال: 1G, 500M):")
    return QUOTA

async def get_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_quota'] = update.message.text
    await update.message.reply_text("⏳ ما هي مدة الاشتراك؟ (مثال: 30d للأيام، 24h للساعات):")
    return DURATION

async def get_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_time'] = update.message.text
    await update.message.reply_text("💰 كم السعر (بالنقاط)؟ (اكتب 0 للمجاني):")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = int(update.message.text)
    data = context.user_data
    
    # حفظ المنتج
    products = load_data(PRODUCTS_FILE)
    prod_id = str(uuid.uuid4())[:8]
    products[prod_id] = {
        "name": data['p_name'],
        "desc": data['p_desc'],
        "media": data['p_media'],
        "media_type": data.get('p_media_type'),
        "proto": data['p_proto'],
        "port": data['p_port'],
        "limit": data['p_limit'],
        "quota": data['p_quota'],
        "time": data['p_time'],
        "price": price
    }
    save_data(PRODUCTS_FILE, products)
    
    await update.message.reply_text("✅ تم إضافة المنتج بنجاح!", reply_markup=ReplyKeyboardMarkup([["🔑 الحصول على كود"], ["⚙️ الإعدادات"]], resize_keyboard=True))
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء", reply_markup=ReplyKeyboardMarkup([["🔑 الحصول على كود"]], resize_keyboard=True))
    return ConversationHandler.END

# --- قائمة المستخدم (الحصول على كود) ---
async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    products = load_data(PRODUCTS_FILE)
    if not products:
        await update.message.reply_text("⚠️ لا توجد منتجات متاحة حالياً.")
        return

    keyboard = []
    for pid, info in products.items():
        btn_text = f"{info['name']} | 💰 {info['price']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"buy_{pid}")])
    
    await update.message.reply_text("🛒 اختر الباقة المناسبة:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- عملية الشراء والتوليد ---
async def handle_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    prod_id = query.data.split("_")[1]
    products = load_data(PRODUCTS_FILE)
    prod = products.get(prod_id)
    
    if not prod:
        await query.edit_message_text("❌ المنتج غير موجود.")
        return

    # عرض التفاصيل
    msg = f"📦 *{prod['name']}*\n📝 {prod['desc']}\n\n📡 {prod['proto']} | 📱 {prod['limit']} أجهزة\n💾 {prod['quota']} | ⏳ {prod['time']}\n💰 السعر: {prod['price']} نقطة"
    
    keyboard = [[InlineKeyboardButton("✅ تأكيد الشراء", callback_data=f"confirm_{prod_id}")]]
    
    if prod['media']:
        if prod['media_type'] == 'photo':
            await query.message.reply_photo(photo=prod['media'], caption=msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.message.reply_video(video=prod['media'], caption=msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

async def confirm_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = str(query.from_user.id)
    prod_id = query.data.split("_")[1]
    
    products = load_data(PRODUCTS_FILE)
    users = load_data(USERS_FILE)
    prod = products.get(prod_id)
    
    # 1. التحقق من الرصيد
    user_points = users.get(user_id, {}).get("points", 0)
    if user_points < prod['price']:
        await query.answer("❌ رصيدك غير كافٍ!", show_alert=True)
        return

    await query.answer("⏳ جاري إنشاء الكود...", show_alert=False)
    
    # 2. حساب القيم
    # تحويل السعة لبايت
    q_str = prod['quota'].upper()
    size = int(''.join(filter(str.isdigit, q_str)))
    max_bytes = size * 1024 * 1024 * 1024 if "G" in q_str else size * 1024 * 1024
    
    # تحويل الوقت لثواني وحساب وقت الانتهاء
    t_str = prod['time'].lower()
    t_val = int(''.join(filter(str.isdigit, t_str)))
    seconds = t_val * 86400 if "d" in t_str else t_val * 3600
    exp_time = int(time.time()) + seconds
    
    # 3. إنشاء الكود في Xray
    uuid_code = subprocess.check_output("xray uuid", shell=True).decode().strip()
    ip = subprocess.check_output("curl -s ifconfig.me", shell=True).decode().strip()
    
    # تنسيق الإيميل الجديد (يحتوي كل المعلومات للمراقب)
    # email: limit_DEVICES_max_BYTES_exp_TIMESTAMP_uuidPrefix
    email = f"limit_{prod['limit']}_max_{max_bytes}_exp_{exp_time}_{uuid_code[:5]}"
    
    try:
        config_path = "/usr/local/etc/xray/config.json"
        with open(config_path, 'r') as f: config = json.load(f)
        
        config['inbounds'][0]['settings']['clients'].append({"id": uuid_code, "email": email})
        
        with open(config_path, 'w') as f: json.dump(config, f, indent=4)
        os.system("systemctl restart xray")
        
        # 4. خصم الرصيد
        if user_id not in users: users[user_id] = {"points": 0}
        users[user_id]["points"] -= prod['price']
        save_data(USERS_FILE, users)
        
        # 5. إرسال الكود
        link = f"vless://{uuid_code}@{ip}:80?path=%2Fmyvless&security=none&encryption=none&type=ws#{prod['name']}"
        await query.message.reply_text(f"✅ تم الشراء بنجاح!\n\n`{link}`", parse_mode='Markdown')
        
    except Exception as e:
        await query.message.reply_text(f"❌ خطأ: {e}")

# --- تشغيل البوت ---
if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()

    # معالج إضافة المنتج
    add_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة كودات"), add_product_start)],
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
        },
        fallbacks=[MessageHandler(filters.Regex("^🔙"), cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ الإعدادات$"), admin_settings))
    app.add_handler(MessageHandler(filters.Regex("^🔙 رجوع$"), start))
    app.add_handler(MessageHandler(filters.Regex("^🔑 الحصول على كود$"), show_products))
    app.add_handler(CallbackQueryHandler(handle_buy, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(confirm_buy, pattern="^confirm_"))
    app.add_handler(add_handler)
    
    print("✅ المتجر يعمل...")
    app.run_polling()
