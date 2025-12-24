#!/bin/bash

# ==========================================
# 1. تحديث النظام وتثبيت المتطلبات
# ==========================================
echo "🔄 جاري تحديث النظام وتثبيت الأدوات..."
apt update && apt upgrade -y
apt install python3-pip python3-venv curl jq ufw net-tools socat nano -y

# فتح البورتات الضرورية في الجدار الناري
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 1000:65000/tcp
ufw --force enable

# ==========================================
# 2. تثبيت Xray Core
# ==========================================
echo "💎 جاري تثبيت Xray..."
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# إنشاء مجلدات اللوج
mkdir -p /var/log/xray
touch /var/log/xray/access.log
touch /var/log/xray/error.log
chmod 666 /var/log/xray/*.log

# ==========================================
# 3. إعداد Xray Config الأساسي (مع API للمراقبة)
# ==========================================
echo "⚙️ ضبط إعدادات Xray..."
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {
        "access": "/var/log/xray/access.log",
        "error": "/var/log/xray/error.log",
        "loglevel": "warning"
    },
    "api": {
        "tag": "api",
        "services": [
            "StatsService"
        ]
    },
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
            "settings": {
                "address": "127.0.0.1"
            },
            "tag": "api"
        }
    ],
    "outbounds": [
        {
            "protocol": "freedom",
            "settings": {}
        }
    ],
    "routing": {
        "rules": [
            {
                "inboundTag": [
                    "api"
                ],
                "outboundTag": "api",
                "type": "field"
            }
        ]
    }
}
EOF

systemctl restart xray

# ==========================================
# 4. إعداد بيئة البوت (Python)
# ==========================================
echo "🐍 تثبيت مكتبات بايثون..."
pip3 install python-telegram-bot --break-system-packages

# طلب معلومات البوت
echo "------------------------------------------------"
read -p "🤖 أدخل توكن البوت (Bot Token): " BOT_TOKEN
read -p "👤 أدخل الأيدي الخاص بك (Admin ID): " MY_ID
echo "------------------------------------------------"

# إنشاء مجلد المشروع
mkdir -p /etc/my-v2ray

# إنشاء ملف الإعدادات
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# إنشاء ملفات الداتا
echo "{}" > /etc/my-v2ray/products.json
# منح المدير رصيد افتراضي كبير للتجربة
echo "{\"$MY_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# إنشاء ملفات فارغة للكود (سيتم تعبئتها يدوياً لاحقاً)
touch /etc/my-v2ray/core.py
touch /etc/my-v2ray/monitor.py

# ==========================================
# 5. إعداد خدمات النظام (Systemd)
# ==========================================
echo "service إعداد ملفات الخدمة..."

# خدمة البوت
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/my-v2ray
ExecStart=/usr/bin/python3 /etc/my-v2ray/core.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# خدمة المراقبة
cat <<EOF > /etc/systemd/system/v2ray-monitor.service
[Unit]
Description=V2Ray Usage Monitor
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/my-v2ray
ExecStart=/usr/bin/python3 /etc/my-v2ray/monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# تفعيل الخدمات
systemctl daemon-reload
systemctl enable v2ray-bot
systemctl enable v2ray-monitor
systemctl enable xray

# ==========================================
# 6. النهاية
# ==========================================
echo "✅ تم تثبيت الأساسيات بنجاح!"
echo ""
echo "⚠️  هام جداً: يجب عليك الآن نسخ أكواد بايثون ولصقها في الملفات التالية:"
echo "1. ملف البوت: nano /etc/my-v2ray/core.py"
echo "2. ملف المراقبة: nano /etc/my-v2ray/monitor.py"
echo ""
echo "بعد لصق الأكواد وحفظها، قم بتشغيل البوت بالأوامر التالية:"
echo "systemctl start v2ray-bot"
echo "systemctl start v2ray-monitor"
