import os, subprocess, json, sys, uuid, random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler, ContextTypes

# إعدادات المسارات
sys.path.append('/etc/my-v2ray')
try:
    from config import TOKEN, ADMIN_ID
except:
    sys.exit("❌ ملف config.py غير موجود")

FILES = {
    "prods": "/etc/my-v2ray/products.json",
    "users": "/etc/my-v2ray/users.json",
    "xray": "/usr/local/etc/xray/config.json"
}

(NAME, PROTOCOL, PRICE) = range(3)

def load_json(p):
    try:
        with open(p, 'r') as f: return json.load(f)
    except: return {}

def save_json(p, d):
    with open(p, 'w') as f: json.dump(d, f, indent=4)

def restart_xray():
    os.system("systemctl restart xray")

# --- الأوامر الأساسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == int(ADMIN_ID):
        kb = [["➕ إضافة منتج", "🛒 المتجر"], ["🔄 ريستارت Xray"]]
        await update.message.reply_text("🛠️ لوحة التحكم (نظام Fallback):", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        await update.message.reply_text("👋 مرحباً بك في بوت البيع.", reply_markup=ReplyKeyboardMarkup([["🛒 المتجر"]], resize_keyboard=True))

# --- إضافة المنتج ---
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("1️⃣ اسم المنتج (مثلاً: تروجان سريع):")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_name'] = update.message.text
    kb = [["vless", "trojan"], ["vmess", "shadowsocks"]]
    await update.message.reply_text("2️⃣ اختر نوع البروتوكول:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return PROTOCOL

async def get_proto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['p_proto'] = update.message.text
    await update.message.reply_text("3️⃣ السعر بالنقاط:")
    return PRICE

async def get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text)
        prods = load_json(FILES['prods'])
        pid = str(uuid.uuid4())[:8]
        
        # تعيين المسار تلقائياً بناءً على النوع
        proto = context.user_data['p_proto']
        path = "/" if proto == "vless" else f"/{proto}"
        if proto == "shadowsocks": path = "/ss"

        prods[pid] = {
            "name": context.user_data['p_name'],
            "proto": proto,
            "price": price,
            "path": path
        }
        save_json(FILES['prods'], prods)
        await update.message.reply_text(f"✅ تم حفظ {proto} على بورت 80 بنجاح!", reply_markup=ReplyKeyboardMarkup([["🛒 المتجر"]], resize_keyboard=True))
        return ConversationHandler.END
    except: return PRICE

# --- الشراء وتوليد الروابط ---
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prods = load_json(FILES['prods'])
    if not prods:
        await update.message.reply_text("المتجر فارغ حالياً.")
        return
    for pid, p in prods.items():
        kb = [[InlineKeyboardButton(f"شراء ({p['price']}💰)", callback_data=f"buy_{pid}")]]
        await update.message.reply_text(f"📦 {p['name']}\n🚀 {p['proto']} | 🔌 Port 80", reply_markup=InlineKeyboardMarkup(kb))

async def process_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    pid = query.data.split("_")[1]
    p = load_json(FILES['prods']).get(pid)
    uid = str(query.from_user.id)
    
    f_uuid = str(uuid.uuid4())
    f_addr = subprocess.getoutput("curl -s ifconfig.me")
    
    # تحديد الـ Tag الصحيح في Xray
    tag_map = {"vless": "vless_main", "trojan": "trojan_internal", "vmess": "vmess_internal", "shadowsocks": "ss_internal"}
    target_tag = tag_map.get(p['proto'])

    config = load_json(FILES['xray'])
    for ib in config['inbounds']:
        if ib.get('tag') == target_tag:
            email = f"u_{uid}_{random.randint(100,999)}"
            if p['proto'] == "shadowsocks":
                ib['settings']['users'].append({"password": f_uuid, "email": email})
            else:
                key = "password" if p['proto'] == "trojan" else "id"
                ib['settings']['clients'].append({key: f_uuid, "email": email})
            break
            
    save_json(FILES['xray'], config)
    restart_xray()
    
    # توليد الرابط النهائي
    link = ""
    name = p['name'].replace(" ", "_")
    if p['proto'] == "vless":
        link = f"vless://{f_uuid}@{f_addr}:80?type=ws&security=none&path=/#{name}"
    elif p['proto'] == "trojan":
        link = f"trojan://{f_uuid}@{f_addr}:80?type=ws&security=none&path=/trojan#{name}"
    elif p['proto'] == "vmess":
        vj = {"v":"2","ps":name,"add":f_addr,"port":"80","id":f_uuid,"aid":"0","net":"ws","path":"/vmess","tls":"none"}
        link = "vmess://" + subprocess.getoutput(f"echo '{json.dumps(vj)}' | base64 -w 0")
    elif p['proto'] == "shadowsocks":
        raw = f"chacha20-ietf-poly1305:{f_uuid}"
        b64 = subprocess.getoutput(f"echo -n '{raw}' | base64 -w 0")
        link = f"ss://{b64}@{f_addr}:80?plugin=v2ray-plugin%3Bpath%3D%2Fss%3Bhost%3D#{name}"

    await query.message.reply_text(f"✅ تم استلام طلبك:\n\n`{link}`", parse_mode='Markdown')

def main():
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة منتج"), add_start)],
        states={NAME: [MessageHandler(filters.TEXT, get_name)], PROTOCOL: [MessageHandler(filters.TEXT, get_proto)], PRICE: [MessageHandler(filters.TEXT, get_price)]},
        fallbacks=[]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.Regex("^🛒 المتجر"), shop))
    app.add_handler(CallbackQueryHandler(process_buy, pattern="^buy_"))
    app.add_handler(MessageHandler(filters.Regex("^🔄 ريستارت Xray"), lambda u,c: (restart_xray(), u.message.reply_text("✅ تم!"))))
    app.run_polling()

if __name__ == '__main__': main()
