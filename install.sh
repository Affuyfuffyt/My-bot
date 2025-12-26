#!/bin/bash

# ألوان للتنسيق
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}🧹 جاري تنظيف السيرفر من أي نسخة قديمة...${NC}"
systemctl stop xray 2>/dev/null
systemctl stop v2ray-bot 2>/dev/null
fuser -k 80/tcp 2>/dev/null # قتل أي عملية تشغل بورت 80

# 1. تثبيت المتطلبات
echo -e "${GREEN}📦 تثبيت التحديثات والمكتبات...${NC}"
apt update && apt install python3-pip curl jq ufw socat -y

# 2. تثبيت Xray Core الرسمي
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 3. إنشاء المجلدات
mkdir -p /etc/my-v2ray
mkdir -p /usr/local/etc/xray

# 4. كتابة ملف Config الذهبي (Fallback System)
# هذا الكود يوزع الحركة: VLESS على / ، Trojan على /trojan ، Vmess على /vmess
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
                    { "path": "/vmess", "dest": 10002, "xver": 1 }
                ]
            },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/" } }
        },
        {
            "port": 10001,
            "listen": "127.0.0.1",
            "protocol": "trojan",
            "tag": "trojan_internal",
            "settings": { "clients": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/trojan" }, "sockopt": { "acceptProxyProtocol": true } }
        },
        {
            "port": 10002,
            "listen": "127.0.0.1",
            "protocol": "vmess",
            "tag": "vmess_internal",
            "settings": { "clients": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/vmess" }, "sockopt": { "acceptProxyProtocol": true } }
        }
    ],
    "outbounds": [{ "protocol": "freedom" }]
}
EOF

# 5. طلب بيانات البوت
echo -e "${GREEN}🤖 إعداد بيانات البوت...${NC}"
read -p "Token: " BOT_TOKEN
read -p "Admin ID: " ADMIN_ID

echo "TOKEN = \"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID = $ADMIN_ID" >> /etc/my-v2ray/config.py
echo "{}" > /etc/my-v2ray/products.json
echo "{\"$ADMIN_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# 6. تثبيت المكتبات
pip3 install python-telegram-bot --break-system-packages

# 7. تشغيل الخدمات
systemctl daemon-reload
systemctl restart xray
systemctl enable xray

echo -e "${GREEN}✅ تم التنظيف والتثبيت بنجاح!${NC}"
echo -e "${GREEN}الآن ارفع ملف core.py وشغل خدمة البوت.${NC}"
