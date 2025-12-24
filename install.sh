#!/bin/bash

# --- 1. تحديث النظام وتثبيت المتطلبات ---
echo "🔄 جاري تحديث السيرفر وتثبيت الأدوات الأساسية..."
apt update && apt upgrade -y
apt install python3-pip python3-venv curl jq ufw net-tools socat nano -y

# فتح البورتات
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# --- 2. تثبيت Xray Core ---
echo "💎 جاري تثبيت Xray Core..."
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# تجهيز مجلدات اللوج
mkdir -p /var/log/xray
touch /var/log/xray/access.log /var/log/xray/error.log
chmod 666 /var/log/xray/*.log

# --- 3. تثبيت "الملف الذهبي" لـ Xray (بورت 80 الموحد) ---
echo "⚙️ برمجة ملف Config الذهبي..."
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {
        "access": "/var/log/xray/access.log",
        "error": "/var/log/xray/error.log",
        "loglevel": "warning"
    },
    "api": {
        "tag": "api",
        "services": ["StatsService"]
    },
    "stats": {},
    "policy": {
        "levels": {
            "0": {
                "statsUserUplink": true,
                "statsUserDownlink": true
            }
        },
        "system": {
            "statsInboundUplink": true,
            "statsInboundDownlink": true
        }
    },
    "inbounds": [
        {
            "listen": "127.0.0.1",
            "port": 10085,
            "protocol": "dokodemo-door",
            "settings": { "address": "127.0.0.1" },
            "tag": "api"
        },
        {
            "port": 80,
            "protocol": "vless",
            "settings": { "clients": [], "decryption": "none" },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/vless" } },
            "tag": "inbound_80_vless"
        },
        {
            "port": 80,
            "protocol": "vmess",
            "settings": { "clients": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/vmess" } },
            "tag": "inbound_80_vmess"
        },
        {
            "port": 80,
            "protocol": "trojan",
            "settings": { "clients": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/trojan" } },
            "tag": "inbound_80_trojan"
        },
        {
            "port": 80,
            "protocol": "shadowsocks",
            "settings": { "method": "chacha20-ietf-poly1305", "users": [] },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/ss" } },
            "tag": "inbound_80_ss"
        }
    ],
    "outbounds": [
        { "protocol": "freedom", "tag": "direct" },
        { "protocol": "blackhole", "tag": "block" }
    ],
    "routing": {
        "rules": [
            { "inboundTag": ["api"], "outboundTag": "api", "type": "field" }
        ]
    }
}
EOF

# ريستارت للتأكد من عمل الإعدادات
systemctl restart xray

# --- 4. إعداد بيئة البوت ---
echo "🐍 تجهيز ملفات البوت..."
pip3 install python-telegram-bot --break-system-packages

mkdir -p /etc/my-v2ray
echo "------------------------------------------------"
read -p "🤖 أدخل توكن البوت: " BOT_TOKEN
read -p "👤 أدخل الأيدي الخاص بك: " MY_ID
echo "------------------------------------------------"

echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

echo "{}" > /etc/my-v2ray/products.json
echo "{\"$MY_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# إنشاء ملفات الكود فارغة ليتم ملؤها لاحقاً
touch /etc/my-v2ray/core.py
touch /etc/my-v2ray/monitor.py

# --- 5. خدمات النظام ---
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

systemctl daemon-reload
systemctl enable v2ray-bot
systemctl enable xray

echo "✅ تم التثبيت بنجاح!"
echo "الملف الذهبي تم وضعه تلقائياً في مسار Xray."
echo "الآن قم بوضع كود core.py في مكانه وشغل الخدمة."
