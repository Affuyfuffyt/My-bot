#!/bin/bash

# 1. تحديث النظام وتثبيت الأدوات الضرورية (conntrack مهم جداً لقطع الاتصال اللحظي)
apt update && apt install python3-pip python3-venv curl jq ufw net-tools conntrack lsof -y
ufw allow 80/tcp
ufw --force enable

# 2. حل مشكلة تعارض المنافذ في Ubuntu 24
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت محرك Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إعداد ملف Xray (VLESS WS Port 80) مع تفعيل ملف السجل الخارجي
mkdir -p /var/log/xray
mkdir -p /usr/local/etc/xray
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {
        "access": "/var/log/xray/access.log",
        "loglevel": "info"
    },
    "inbounds": [{
        "port": 80,
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
    }],
    "outbounds": [{"protocol": "freedom"}]
}
EOF

# إنشاء ملف السجل ومنحه الصلاحيات اللازمة ليقرأه البوت
touch /var/log/xray/access.log
chmod 666 /var/log/xray/access.log
systemctl restart xray

# 5. تثبيت مكتبة التليجرام
pip install python-telegram-bot --upgrade --break-system-packages

# 6. طلب بيانات البوت من المستخدم
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID) الخاص بك: " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 7. تحميل ملف البوت الأساسي (core.py) من مستودعك
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 8. إنشاء سكريبت المراقبة (monitor.py) - النسخة اللحظية الفولاذية
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess

def enforce_limit():
    print("نظام الحظر الفولاذي يعمل الآن... الفحص كل 0.5 ثانية.")
    blocked_ips = {} # {ip: timestamp}

    while True:
        try:
            # قراءة آخر 100 سطر من ملف السجل مباشرة (سرعة فائقة)
            if not os.path.exists("/var/log/xray/access.log"):
                time.sleep(1)
                continue
                
            with open("/var/log/xray/access.log", "r") as f:
                lines = f.readlines()[-100:]
            
            user_ips = {} # {email: set(ips)}
            user_limits = {} # {email: int}

            for line in lines:
                if "accepted" in line and "email: limit_" in line:
                    try:
                        # استخراج البيانات من السجل
                        parts = line.split("email: limit_")[1]
                        limit = int(parts.split("_")[0])
                        email = "limit_" + parts.split()[0]
                        ip = line.split("from:")[1].split(":")[0].strip()
                        
                        if email not in user_ips:
                            user_ips[email] = set()
                            user_limits[email] = limit
                        user_ips[email].add(ip)
                    except: continue

            # منطق الحظر والسحق
            for email, ips in user_ips.items():
                limit = user_limits[email]
                active_ips = list(ips)
                
                # إذا كان الحد 0 (منع كامل) أو الأجهزة أكثر من الحد
                if limit == 0 or len(active_ips) > limit:
                    to_block = active_ips if limit == 0 else active_ips[limit:]
                    for target in to_block:
                        if target not in blocked_ips:
                            # حظر في الجدار الناري + قتل الجلسة النشطة فوراً
                            os.system(f"iptables -I INPUT -p tcp -s {target} --dport 80 -j DROP")
                            os.system(f"conntrack -D -s {target} > /dev/null 2>&1")
                            blocked_ips[target] = time.time()
                            print(f"🚫 تم سحق اتصال مخالف: {target} للمستخدم {email} (الحد: {limit})")

            # فك الحظر التلقائي بعد 30 ثانية للسماح بإعادة المحاولة إذا أغلق المستخدم جهازه الأصلي
            now = time.time()
            for ip, t in list(blocked_ips.items()):
                if now - t > 30:
                    os.system(f"iptables -D INPUT -p tcp -s {ip} --dport 80 -j DROP")
                    del blocked_ips[ip]
                    print(f"♻️ فك الحظر المؤقت عن {ip} للمراجعة.")

        except Exception as e:
            pass
        
        time.sleep(0.5)

if __name__ == '__main__':
    enforce_limit()
EOF

# 9. إعداد خدمات النظام (Services) لتعمل تلقائياً
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray Bot Service
After=network.target
[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/core.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

cat <<EOF > /etc/systemd/system/v2ray-monitor.service
[Unit]
Description=V2Ray Fast Monitor
After=network.target
[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/monitor.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# 10. التشغيل النهائي وتصفير الجدار الناري
iptables -F
systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl restart v2ray-bot v2ray-monitor

echo "✅ اكتمل التثبيت بنجاح!"
echo "📡 نظام المراقبة الفولاذي يعمل الآن (فحص كل 0.5 ثانية)."
