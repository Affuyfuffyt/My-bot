#!/bin/bash

# 1. تحديث النظام وفتح بورت 80
apt update && apt install python3-pip python3-venv curl jq ufw -y
ufw allow 80/tcp
ufw --force enable

# 2. حل مشكلة تعارض المنافذ
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت محرك Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. ضبط الإعدادات على بورت 80 (VLESS WS)
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {"loglevel": "info"},
    "inbounds": [{
        "port": 80,
        "protocol": "vless",
        "settings": {"clients": [], "decryption": "none"},
        "streamSettings": {
            "network": "ws",
            "wsSettings": {"path": "/myvless"}
        }
    }],
    "outbounds": [{"protocol": "freedom"}]
}
EOF

systemctl restart xray

# 5. تثبيت مكتبة البوت
pip install python-telegram-bot --break-system-packages

# 6. حفظ البيانات وتحميل البوت
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 7. تشغيل البوت كخدمة
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

systemctl daemon-reload && systemctl enable v2ray-bot.service && systemctl start v2ray-bot.service
echo "✅ تم التحديث لبورت 80! جرب الآن."
