#!/bin/bash

# 1. تحديث النظام وتثبيت المتطلبات
apt update && apt install python3-pip python3-venv curl jq -y
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 2. إنشاء ملف إعدادات Xray (VLESS WS على منفذ 443)
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {
        "loglevel": "info"
    },
    "inbounds": [
        {
            "port": 443,
            "protocol": "vless",
            "settings": {
                "clients": [],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "ws",
                "wsSettings": {
                    "path": "/myvless"
                }
            }
        }
    ],
    "outbounds": [
        {
            "protocol": "freedom"
        }
    ]
}
EOF

# فتح بورت 443 في جدار الحماية
ufw allow 443/tcp
systemctl restart xray

# 3. تثبيت مكتبة التليجرام
pip install python-telegram-bot --break-system-packages

# 4. طلب بيانات البوت
echo "-----------------------------------------------"
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل معرف الأدمن (ID): " MY_ID
echo "-----------------------------------------------"

# 5. حفظ الإعدادات
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 6. تحميل ملف البوت core.py من حسابك
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 7. تشغيل البوت كخدمة دائمية
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray WS Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/core.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable v2ray-bot.service
systemctl start v2ray-bot.service

echo "✅ تم التثبيت بالكامل! جرب البوت الآن."
