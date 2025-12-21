#!/bin/bash

# تثبيت المتطلبات الأساسية ومحرك Xray
apt update && apt install python3-pip python3-venv curl -y
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# تثبيت مكتبة التليجرام
pip install python-telegram-bot --break-system-packages

# طلب البيانات من المستخدم
echo "--- إعداد البوت ---"
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID

# إنشاء المجلد وحفظ الإعدادات
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# تحميل ملف البوت (تأكد أن اسم الملف core.py موجود في حسابك)
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/refs/heads/main/core.py"

# إنشاء الخدمة ليعمل البوت تلقائياً
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/core.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# تفعيل وتشغيل الخدمة
systemctl daemon-reload
systemctl enable v2ray-bot.service
systemctl start v2ray-bot.service

echo "✅ اكتمل التثبيت بنجاح! اذهب للبوت الآن."
