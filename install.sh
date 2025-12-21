#!/bin/bash

# 1. تحديث النظام وتجهيز البيئة
apt update && apt install python3-pip python3-venv curl jq ufw -y
ufw allow 80/tcp
ufw --force enable

# 2. إيقاف التعارض مع منافذ Ubuntu 24
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت محرك Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إعداد ملف Xray (VLESS WS Port 80)
mkdir -p /usr/local/etc/xray
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

# 5. تثبيت مكتبة التليجرام
pip install python-telegram-bot --break-system-packages

# 6. طلب بيانات البوت وحفظها
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 7. تحميل الكود البرمجي للبوت
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 8. إنشاء سكريبت مراقبة الأجهزة (Monitor)
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess

def enforce_limit():
    while True:
        try:
            # فحص سجلات الاتصال لآخر 15 ثانية
            cmd = "journalctl -u xray --since '15 seconds ago' | grep 'accepted' | tail -n 30"
            logs = subprocess.check_output(cmd, shell=True).decode()
            
            user_ips = {}
            for line in logs.split('\n'):
                if 'email: limit_' in line:
                    parts = line.split('email: limit_')[1]
                    limit = int(parts.split('_')[0])
                    email = "limit_" + parts.split()[0]
                    ip = line.split('from:')[1].split(':')[0].strip()
                    
                    if email not in user_ips: 
                        user_ips[email] = {"limit": limit, "ips": []}
                    if ip not in user_ips[email]["ips"]: 
                        user_ips[email]["ips"].append(ip)
            
            for email, data in user_ips.items():
                if len(data["ips"]) > data["limit"]:
                    target_ip = data["ips"][-1]
                    os.system(f"iptables -A INPUT -s {target_ip} -j DROP")
                    time.sleep(10)
                    os.system(f"iptables -D INPUT -s {target_ip} -j DROP")
        except: pass
        time.sleep(2)

if __name__ == '__main__': enforce_limit()
EOF

# 9. إنشاء خدمات النظام
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
Description=V2Ray IP Monitor
After=network.target
[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/monitor.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# 10. التشغيل النهائي
systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl start v2ray-bot v2ray-monitor

echo "✅ تم التثبيت بنجاح! البوت يعمل الآن على بورت 80 مع نظام مراقبة الأجهزة."
