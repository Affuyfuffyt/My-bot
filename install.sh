#!/bin/bash

# الألوان للتنسيق
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔄 جاري بدء تثبيت الأداة (نظام الـ Fallback)...${NC}"

# 1. تحديث السيرفر وتثبيت المتطلبات
apt update && apt upgrade -y
apt install python3-pip python3-venv curl jq ufw socat nano -y

# 2. فتح البورتات
ufw allow 22/tcp
ufw allow 80/tcp
ufw --force enable

# 3. تثبيت Xray Core
echo -e "${BLUE}💎 جاري تثبيت Xray Core...${NC}"
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إنشاء المجلدات اللازمة
mkdir -p /etc/my-v2ray
mkdir -p /var/log/xray

# 5. كتابة الملف الذهبي (config.json)
echo -e "${BLUE}⚙️ برمجة ملف Config الذهبي (بورت 80)...${NC}"
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
        },
        {
            "port": 10003,
            "listen": "127.0.0.1",
            "protocol": "shadowsocks",
            "tag": "ss_internal",
            "settings": { "method": "chacha20-ietf-poly1305", "users": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/ss" }, "sockopt": { "acceptProxyProtocol": true } }
        }
    ],
    "outbounds": [{ "protocol": "freedom" }]
}
EOF

# 6. تثبيت مكتبة التليجرام
pip3 install python-telegram-bot --break-system-packages

# 7. طلب بيانات البوت من المستخدم
echo -e "${GREEN}------------------------------------------------${NC}"
read -p "🤖 أدخل توكن البوت (Token): " BOT_TOKEN
read -p "👤 أدخل الأيدي (Your ID): " MY_ID
echo -e "${GREEN}------------------------------------------------${NC}"

# 8. إنشاء ملف config.py
cat <<EOF > /etc/my-v2ray/config.py
TOKEN = "$BOT_TOKEN"
ADMIN_ID = $MY_ID
EOF

# 9. إنشاء ملفات البيانات فارغة
echo "{}" > /etc/my-v2ray/products.json
echo "{\"$MY_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# 10. إنشاء خدمة النظام (Systemd) لضمان عمل البوت 24 ساعة
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

# 11. تشغيل الخدمات
systemctl daemon-reload
systemctl restart xray
systemctl enable xray
systemctl enable v2ray-bot

echo -e "${GREEN}✅ تم تثبيت السيرفر والملف الذهبي بنجاح!${NC}"
echo -e "${GREEN}🚀 الآن تأكد من رفع ملف core.py إلى مسار /etc/my-v2ray/ وشغل البوت.${NC}"
