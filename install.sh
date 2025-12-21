#!/bin/bash

# 1. تحديث النظام وتثبيت الأدوات الأساسية
apt update && apt install python3-pip python3-venv curl jq ufw -y
ufw allow 80/tcp
ufw --force enable

# 2. حل مشكلة تعارض المنافذ في Ubuntu 24
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت محرك Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إعداد ملف Xray (VLESS WS Port 80) مع تفعيل السجلات INFO
mkdir -p /usr/local/etc/xray
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {
        "loglevel": "info",
        "access": "/var/log/xray/access.log",
        "error": "/var/log/xray/error.log"
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
    "outbounds": [{
        "protocol": "freedom"
    }]
}
EOF

# إنشاء مجلد السجلات وتصحيح الصلاحيات
mkdir -p /var/log/xray
touch /var/log/xray/access.log
chmod 666 /var/log/xray/access.log
systemctl restart xray

# 5. تثبيت مكتبة التليجرام المحدثة
pip install python-telegram-bot --upgrade --break-system-packages

# 6. طلب بيانات البوت
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 7. تحميل ملف البوت الأساسي (core.py)
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 8. إنشاء سكريبت المراقبة الديناميكي (monitor.py)
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess

def get_active_sessions():
    # جلب الـ IPs المتصلة من سجلات Xray مباشرة لآخر 10 ثوانٍ
    cmd = "journalctl -u xray --since '10 seconds ago' | grep 'accepted' | tail -n 50"
    try:
        logs = subprocess.check_output(cmd, shell=True).decode()
        active = {}
        for line in logs.split('\n'):
            if 'email: limit_' in line:
                try:
                    parts = line.split('email: limit_')[1]
                    limit = int(parts.split('_')[0])
                    email = "limit_" + parts.split()[0]
                    ip = line.split('from:')[1].split(':')[0].strip()
                    
                    if email not in active: active[email] = {"limit": limit, "ips": set()}
                    active[email]["ips"].add(ip)
                except: continue
        return active
    except: return {}

def enforce_dynamic_limit():
    blocked_ips = {} 
    print("نظام المراقبة الديناميكي بدأ العمل...")
    
    while True:
        active_users = get_active_sessions()
        
        # 1. فك الحظر إذا توفر مكان (الجهاز الأول خرج)
        for email in list(blocked_ips.keys()):
            limit = blocked_ips[email]["limit"]
            current_ips = active_users.get(email, {"ips": set()})["ips"]
            
            if len(current_ips) < limit:
                for ip in blocked_ips[email]["ips"]:
                    os.system(f"iptables -D INPUT -s {ip} -j DROP")
                print(f"✅ فك الحظر عن أجهزة المستخدم {email} لتوافر مكان.")
                del blocked_ips[email]

        # 2. حظر الأجهزة الزائدة فوراً
        for email, data in active_users.items():
            if len(data["ips"]) > data["limit"]:
                all_ips = list(data["ips"])
                to_block = all_ips[data["limit"]:]
                
                if email not in blocked_ips:
                    blocked_ips[email] = {"limit": data["limit"], "ips": []}
                
                for ip in to_block:
                    if ip not in blocked_ips[email]["ips"]:
                        os.system(f"iptables -A INPUT -s {ip} -j DROP")
                        blocked_ips[email]["ips"].append(ip)
                        print(f"🚫 حظر IP زائد: {ip} للمستخدم {email}")
        
        time.sleep(2)

if __name__ == '__main__':
    enforce_dynamic_limit()
EOF

# 9. إعداد خدمات النظام (Services)
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
Description=V2Ray IP Monitor Dynamic
After=network.target
[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/monitor.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# 10. التفعيل والتشغيل
systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl start v2ray-bot v2ray-monitor

echo "✅ اكتمل التثبيت بنجاح!"
echo "📡 البوت يعمل على بورت 80."
echo "⚖️ نظام المراقبة الديناميكي يعمل (حظر وفك حظر تلقائي)."
