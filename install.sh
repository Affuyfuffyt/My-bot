#!/bin/bash

# 1. تثبيت المتطلبات (أضفنا أدوات التحكم بالـ API والشبكة)
apt update && apt install python3-pip python3-venv curl jq ufw net-tools conntrack -y
ufw allow 80/tcp
ufw allow 10085/tcp # بورت التحكم الداخلي
ufw --force enable

# 2. حل مشكلة تعارض المنافذ
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إعداد ملف Xray (VLESS + Stats API)
mkdir -p /usr/local/etc/xray
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": { "access": "/var/log/xray/access.log", "loglevel": "info" },
    "stats": {},
    "api": { "tag": "api", "services": ["StatsService"] },
    "policy": {
        "levels": { "0": { "statsUserUplink": true, "statsUserDownlink": true } },
        "system": { "statsInboundUplink": true, "statsInboundDownlink": true }
    },
    "inbounds": [
        {
            "port": 80,
            "protocol": "vless",
            "settings": { "clients": [], "decryption": "none" },
            "streamSettings": { "network": "ws", "wsSettings": { "path": "/myvless" } }
        },
        {
            "listen": "127.0.0.1",
            "port": 10085,
            "protocol": "dokodemo-door",
            "settings": { "address": "127.0.0.1" },
            "tag": "api"
        }
    ],
    "outbounds": [{ "protocol": "freedom" }, { "protocol": "blackhole", "tag": "blocked" }],
    "routing": { "rules": [{ "inboundTag": ["api"], "outboundTag": "api", "type": "field" }] }
}
EOF

touch /var/log/xray/access.log
chmod 666 /var/log/xray/access.log
systemctl restart xray

# 5. تثبيت مكتبة التليجرام
pip install python-telegram-bot --upgrade --break-system-packages

# 6. طلب بيانات البوت
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 7. تحميل ملف البوت الأساسي (سأضعه لك في الخطوة القادمة)
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 8. إنشاء "المراقب النووي" (monitor.py) - يراقب الأجهزة + الجيجات
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess, json

def get_stats():
    try:
        cmd = "xray api statsquery --server=127.0.0.1:10085"
        output = subprocess.check_output(cmd, shell=True).decode()
        return json.loads(output)
    except: return None

def enforce_all():
    blocked_ips = {}
    print("نظام المراقبة المزدوج يعمل...")
    
    while True:
        # أولاً: مراقبة سعة البيانات (الجيجات)
        stats = get_stats()
        if stats and 'stat' in stats:
            user_usage = {}
            for s in stats['stat']:
                name = s['name']
                if 'user>>>' in name:
                    email = name.split('>>>')[1]
                    user_usage[email] = user_usage.get(email, 0) + int(s['value'])
            
            for email, used_bytes in user_usage.items():
                if 'max_' in email:
                    try:
                        max_bytes = int(email.split('max_')[1].split('_')[0])
                        if used_bytes >= max_bytes:
                            print(f"🔥 سحق مستخدم انتهت سعة بياناته: {email}")
                            os.system(f"sed -i '/{email}/d' /usr/local/etc/xray/config.json") # حذف من الملف
                            os.system("systemctl restart xray")
                    except: pass

        # ثانياً: مراقبة عدد الأجهزة (نفس النظام اللحظي السابق)
        try:
            with open("/var/log/xray/access.log", "r") as f:
                lines = f.readlines()[-100:]
            for line in lines:
                if "accepted" in line and "email: limit_" in line:
                    parts = line.split("email: limit_")[1]
                    limit = int(parts.split("_")[0])
                    email = "limit_" + parts.split()[0]
                    ip = line.split("from:")[1].split(":")[0].strip()
                    
                    # (هنا نطبق منطق الحظر الذي برمجناه سابقاً للأجهزة)
                    # للتبسيط، نستخدم iptables كما في الكود السابق
                    if limit == 0: 
                         os.system(f"iptables -I INPUT -s {ip} -j DROP")
                         os.system(f"conntrack -D -s {ip} > /dev/null 2>&1")
        except: pass

        time.sleep(5) # فحص كل 5 ثوانٍ للموازنة بين السرعة والأداء

if __name__ == '__main__':
    enforce_all()
EOF

# 9. إعداد الخدمات
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

cat <<EOF > /etc/systemd/system/v2ray-monitor.service
[Unit]
Description=V2Ray Monitor
After=network.target
[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/monitor.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl restart v2ray-bot v2ray-monitor
