#!/bin/bash

# الألوان للتنسيق
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔄 جاري تنظيف السيرفر وبدء التثبيت النظيف...${NC}"
# تنظيف أي عمليات قديمة تشغل البورت 80 لضمان عدم حدوث تعارض
systemctl stop xray 2>/dev/null
systemctl stop v2ray-bot 2>/dev/null
fuser -k 80/tcp 2>/dev/null
lsof -t -i:80 | xargs kill -9 2>/dev/null

# --- 1. تحديث النظام وتثبيت المتطلبات ---
echo -e "${GREEN}📦 تحديث السيرفر وتثبيت الأدوات...${NC}"
apt update && apt upgrade -y
apt install python3-pip python3-venv curl jq ufw net-tools socat nano wget -y

# فتح البورتات الضرورية
ufw allow 22/tcp
ufw allow 80/tcp
ufw --force enable

# --- 2. تثبيت Xray Core ---
echo -e "${GREEN}💎 جاري تثبيت Xray Core الرسمي...${NC}"
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# تجهيز مجلدات اللوج
mkdir -p /var/log/xray
touch /var/log/xray/access.log /var/log/xray/error.log
chmod 666 /var/log/xray/*.log

# --- 3. تثبيت "الملف الذهبي" بنظام Fallback (لعمل كل البروتوكولات على 80) ---
echo -e "${GREEN}⚙️ برمجة ملف Config الذهبي (بورت 80 الموحد)...${NC}"
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {
        "access": "/var/log/xray/access.log",
        "error": "/var/log/xray/error.log",
        "loglevel": "warning"
    },
    "inbounds": [
        {
            "port": 80,
            "protocol": "vless",
            "tag": "vless_main",
            "settings": {
                "clients": [],
                "decryption": "none",
                "fallbacks": [
                    { "path": "/vmess", "dest": 10002, "xver": 1 },
                    { "path": "/trojan", "dest": 10001, "xver": 1 },
                    { "path": "/ss", "dest": 10003, "xver": 1 }
                ]
            },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/" } }
        },
        {
            "port": 10001, "listen": "127.0.0.1", "protocol": "trojan", "tag": "inbound_80_trojan",
            "settings": { "clients": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/trojan" }, "sockopt": { "acceptProxyProtocol": true } }
        },
        {
            "port": 10002, "listen": "127.0.0.1", "protocol": "vmess", "tag": "inbound_80_vmess",
            "settings": { "clients": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/vmess" }, "sockopt": { "acceptProxyProtocol": true } }
        },
        {
            "port": 10003, "listen": "127.0.0.1", "protocol": "shadowsocks", "tag": "inbound_80_ss",
            "settings": { "method": "chacha20-ietf-poly1305", "users": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/ss" }, "sockopt": { "acceptProxyProtocol": true } }
        }
    ],
    "outbounds": [{ "protocol": "freedom", "tag": "direct" }]
}
EOF

systemctl restart xray

# --- 4. إعداد بيئة البوت ---
echo -e "${GREEN}🐍 تجهيز بيئة البايثون...${NC}"
pip3 install python-telegram-bot --break-system-packages

mkdir -p /etc/my-v2ray
echo "------------------------------------------------"
read -p "🤖 أدخل توكن البوت: " BOT_TOKEN
read -p "👤 أدخل الأيدي (ID) الخاص بك: " MY_ID
echo "------------------------------------------------"

echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

echo "{}" > /etc/my-v2ray/products.json
echo "{\"$MY_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# --- 🟢 جلب كود core.py من GitHub الخاص بك تلقائياً ---
echo -e "${GREEN}📥 جاري سحب كود البوت من GitHub...${NC}"
GITHUB_LINK="https://raw.githubusercontent.com/Affuyfuffyt/My-bot/refs/heads/main/core.py"
wget -O /etc/my-v2ray/core.py "$GITHUB_LINK"

# --- 5. إنشاء خدمة النظام للبوت (للبقاء شغال 24 ساعة) ---
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray Bot Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/core.py
WorkingDirectory=/etc/my-v2ray
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}🔄 تشغيل الخدمات...${NC}"
systemctl daemon-reload
systemctl enable v2ray-bot
systemctl start v2ray-bot
systemctl enable xray

echo -e "${BLUE}==============================================${NC}"
echo -e "${GREEN}✅ تم التثبيت بنجاح!${NC}"
echo -e "${GREEN}🚀 البوت تم سحبه من مستودعك وهو يعمل الآن.${NC}"
echo -e "${BLUE}==============================================${NC}"
