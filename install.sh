#!/bin/bash

# الألوان لتنسيق المخرجات
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}   🚀 سكربت تثبيت بوت البيع (نظام Fallback 80)   ${NC}"
echo -e "${BLUE}==============================================${NC}"

# 1. تنظيف السيرفر من المخلفات السابقة
echo -e "${YELLOW}🧹 جاري تنظيف السيرفر وحذف أي نسخ قديمة...${NC}"
systemctl stop xray 2>/dev/null
systemctl stop v2ray-bot 2>/dev/null
systemctl disable xray 2>/dev/null
rm -f /etc/systemd/system/v2ray-bot.service

# قتل أي عملية تشغل بورت 80 لضمان عدم حدوث تصادم
fuser -k 80/tcp 2>/dev/null
lsof -t -i:80 | xargs kill -9 2>/dev/null

# 2. تحديث النظام وتثبيت المكتبات الضرورية
echo -e "${GREEN}📦 جاري تحديث النظام وتثبيت المتطلبات...${NC}"
apt update && apt upgrade -y
apt install python3-pip python3-venv curl jq ufw socat nano lsof -y

# 3. تثبيت Xray Core (النسخة الرسمية)
echo -e "${GREEN}💎 جاري تثبيت Xray Core...${NC}"
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. فتح البورت 80 في الجدار الناري
echo -e "${GREEN}🛡️ ضبط الجدار الناري (UFW)...${NC}"
ufw allow 22/tcp
ufw allow 80/tcp
ufw --force enable

# 5. إنشاء مجلدات العمل
mkdir -p /etc/my-v2ray
mkdir -p /usr/local/etc/xray

# 6. كتابة ملف Config الذهبي (نظام التوزيع الذكي)
# هنا يكمن السر: بورت 80 يستقبل VLESS ويحول البقية للمداخل الداخلية
echo -e "${GREEN}⚙️ برمجة ملف Config.json بنظام الـ Fallback...${NC}"
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": { "loglevel": "warning" },
    "inbounds": [
        {
            "port": 80,
            "protocol": "vless",
            "tag": "vless_main",
            "settings": {
                "clients": [],
                "decryption": "none",
                "fallbacks": [
                    { "path": "/trojan", "dest": 10001, "xver": 1 },
                    { "path": "/vmess", "dest": 10002, "xver": 1 },
                    { "path": "/ss", "dest": 10003, "xver": 1 }
                ]
            },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/" } }
        },
        {
            "port": 10001, "listen": "127.0.0.1", "protocol": "trojan", "tag": "trojan_internal",
            "settings": { "clients": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/trojan" }, "sockopt": { "acceptProxyProtocol": true } }
        },
        {
            "port": 10002, "listen": "127.0.0.1", "protocol": "vmess", "tag": "vmess_internal",
            "settings": { "clients": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/vmess" }, "sockopt": { "acceptProxyProtocol": true } }
        },
        {
            "port": 10003, "listen": "127.0.0.1", "protocol": "shadowsocks", "tag": "ss_internal",
            "settings": { "method": "chacha20-ietf-poly1305", "users": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/ss" }, "sockopt": { "acceptProxyProtocol": true } }
        }
    ],
    "outbounds": [{ "protocol": "freedom" }]
}
EOF

# 7. تثبيت مكتبة التليجرام (نسخة متوافقة)
pip3 install python-telegram-bot --break-system-packages

# 8. إدخال التوكن والأيدي لإنشاء ملف config.py
echo -e "${YELLOW}------------------------------------------------${NC}"
read -p "🤖 أدخل توكن البوت: " BOT_TOKEN
read -p "👤 أدخل الأيدي (ID) الخاص بك: " ADMIN_ID
echo -e "${YELLOW}------------------------------------------------${NC}"

cat <<EOF > /etc/my-v2ray/config.py
TOKEN = "$BOT_TOKEN"
ADMIN_ID = $ADMIN_ID
EOF

# 9. إنشاء ملفات البيانات الأساسية
echo "{}" > /etc/my-v2ray/products.json
echo "{\"$ADMIN_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# 10. إنشاء خدمة النظام لعمل البوت تلقائياً
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray Telegram Bot Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/core.py
WorkingDirectory=/etc/my-v2ray
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

# 11. إعادة تشغيل الخدمات وتفعيلها
echo -e "${GREEN}🔄 تشغيل الخدمات...${NC}"
systemctl daemon-reload
systemctl restart xray
systemctl enable xray
systemctl enable v2ray-bot

echo -e "${BLUE}==============================================${NC}"
echo -e "${GREEN}✅ تم التثبيت بنجاح! السيرفر الآن نظيف ويعمل.${NC}"
echo -e "${YELLOW}تأكد من وجود ملف core.py في المجلد الرئيسي لـ GitHub.${NC}"
echo -e "${BLUE}==============================================${NC}"
