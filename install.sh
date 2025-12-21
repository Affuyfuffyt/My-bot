#!/bin/bash

# 1. تحديث النظام وتثبيت المتطلبات (أضفنا conntrack لقتل الجلسات فوراً)
apt update && apt install python3-pip python3-venv curl jq ufw net-tools conntrack -y
ufw allow 80/tcp
ufw --force enable

# 2. إعدادات الشبكة لمنع التعارض في Ubuntu 24
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إعداد Xray مع سجلات INFO للرصد السريع
mkdir -p /usr/local/etc/xray
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {
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
    "outbounds": [{
        "protocol": "freedom"
    }]
}
EOF

systemctl restart xray

# 5. تحديث مكتبة التليجرام
pip install python-telegram-bot --upgrade --break-system-packages

# 6. إعداد بيانات البوت
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 7. تحميل كود البوت الأساسي
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 8. إنشاء "المراقب الأشرس" (monitor.py)
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess, json

def get_realtime_connections():
    try:
        # فحص بورت 80 وجلب الـ IPs المتصلة فعلياً
        cmd = "netstat -tnp | grep ':80 ' | grep 'ESTABLISHED' | awk '{print \$5}' | cut -d: -f1"
        output = subprocess.check_output(cmd, shell=True).decode()
        return list(set([ip.strip() for ip in output.split('\n') if ip.strip()]))
    except: return []

def enforce_limit():
    blocked_ips = set()
    print("المراقب الأشرس بدأ العمل.. سيتم سحق أي اتصال مخالف فوراً.")
    
    while True:
        current_active_ips = get_realtime_connections()
        
        # قراءة السجلات بسرعة (آخر 20 سطر فقط)
        cmd_logs = "journalctl -u xray -n 20 --no-pager | grep 'accepted'"
        try:
            logs = subprocess.check_output(cmd_logs, shell=True).decode()
            user_map = {} 
            limits = {}   
            
            for line in logs.split('\n'):
                if 'email: limit_' in line:
                    try:
                        parts = line.split('email: limit_')[1]
                        limit_val = int(parts.split('_')[0])
                        email_key = "limit_" + parts.split()[0]
                        ip_val = line.split('from:')[1].split(':')[0].strip()
                        
                        user_map[ip_val] = email_key
                        limits[email_key] = limit_val
                    except: continue

            # جرد المستخدمين النشطين
            active_users_ips = {} 
            for ip in current_active_ips:
                if ip in user_map:
                    email = user_map[ip]
                    if email not in active_users_ips: active_users_ips[email] = []
                    active_users_ips[email].append(ip)

            # تطبيق الحظر وقطع الاتصال (Kill)
            for email, ips in active_users_ips.items():
                limit = limits.get(email, 999)
                
                if limit == 0 or len(ips) > limit:
                    to_block = ips if limit == 0 else ips[limit:]
                    for target in to_block:
                        if target not in blocked_ips:
                            # 1. حظر الـ IP في الجدار الناري بالمرتبة الأولى
                            os.system(f"iptables -I INPUT -s {target} -j DROP")
                            # 2. قتل الجلسة النشطة فوراً حتى لا يكمل استهلاك البيانات
                            os.system(f"conntrack -D -s {target}") 
                            blocked_ips.add(target)
                            print(f"🔥 سحق اتصال: {target} (المستخدم: {email} - الحد: {limit})")

            # فك الحظر الذكي إذا انقطع الاتصال الفعلي
            for b_ip in list(blocked_ips):
                if b_ip not in current_active_ips:
                    os.system(f"iptables -D INPUT -s {b_ip} -j DROP")
                    blocked_ips.discard(b_ip)
                    print(f"♻️ فك حظر {b_ip} للمراجعة.")

        except: pass
        time.sleep(1) # فحص كل ثانية واحدة

if __name__ == '__main__':
    enforce_limit()
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
Description=V2Ray IP Monitor Dynamic
After=network.target
[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/monitor.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# 10. التفعيل والتشغيل النهائي
iptables -F
systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl start v2ray-bot v2ray-monitor

echo "✅ تم التثبيت بنجاح!"
echo "📡 نظام المراقبة الأشرس مفعل الآن."
