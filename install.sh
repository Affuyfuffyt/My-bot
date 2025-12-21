#!/bin/bash

# 1. تحديث النظام وتثبيت الأدوات (أضفنا net-tools لقراءة الاتصالات)
apt update && apt install python3-pip python3-venv curl jq ufw net-tools -y
ufw allow 80/tcp
ufw --force enable

# 2. حل مشكلة تعارض المنافذ في Ubuntu 24
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت محرك Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إعداد ملف Xray (VLESS WS Port 80) مع تفعيل السجلات INFO بدقة
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

# 5. تثبيت مكتبة التليجرام
pip install python-telegram-bot --upgrade --break-system-packages

# 6. طلب بيانات البوت وحفظها
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 7. تحميل كود البوت (core.py)
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 8. إنشاء سكريبت المراقبة المحدث (monitor.py)
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess

def get_realtime_connections():
    # مراقبة بورت 80 مباشرة لرؤية كل الـ IPs المتصلة حالياً
    try:
        cmd = "netstat -tnp | grep ':80 ' | grep 'ESTABLISHED' | awk '{print \$5}' | cut -d: -f1"
        output = subprocess.check_output(cmd, shell=True).decode()
        return [ip.strip() for ip in output.split('\n') if ip.strip()]
    except: return []

def enforce_limit():
    print("المراقب الذكي يعمل بنظام التفتيش المباشر...")
    blocked_ips = set() # الـ IPs المحظورة حالياً

    while True:
        connections = get_realtime_connections()
        unique_active_ips = set(connections)
        
        # قراءة سجلات Xray لمعرفة أي IP يتبع لأي مستخدم والحد المسموح له
        cmd_logs = "journalctl -u xray --since '10 seconds ago' | grep 'accepted'"
        try:
            logs = subprocess.check_output(cmd_logs, shell=True).decode()
            user_data = {} # {email: {"limit": int, "ips": set()}}
            
            for line in logs.split('\n'):
                if 'email: limit_' in line:
                    try:
                        parts = line.split('email: limit_')[1]
                        limit = int(parts.split('_')[0])
                        email = "limit_" + parts.split()[0]
                        ip = line.split('from:')[1].split(':')[0].strip()
                        
                        # نركز فقط على الـ IPs التي لا تزال متصلة فعلياً حسب Netstat
                        if ip in unique_active_ips:
                            if email not in user_data: user_data[email] = {"limit": limit, "ips": set()}
                            user_data[email]["ips"].add(ip)
                    except: continue

            # الحظر وفك الحظر التلقائي
            for email, data in user_data.items():
                active_list = list(data["ips"])
                limit = data["limit"]

                # 🚫 حالة التجاوز: حظر الجهاز الزائد
                if len(active_list) > limit:
                    to_block = active_list[limit:] # الأجهزة التي تزيد عن الحد
                    for tip in to_block:
                        if tip not in blocked_ips:
                            os.system(f"iptables -I INPUT -s {tip} -j DROP")
                            blocked_ips.add(tip)
                            print(f"🚫 تم حظر IP زائد: {tip} للمستخدم {email}")

            # ✅ فك الحظر: إذا قل عدد الأجهزة المتصلة عن الحد
            for b_ip in list(blocked_ips):
                # إذا كان الـ IP المحظور لم يعد يظهر كجهاز زائد أو خرج أحد الأجهزة الأصلية
                # نقوم بفك الحظر لتجربة الاتصال مرة أخرى
                found_in_active = False
                for email, data in user_data.items():
                    if b_ip in data["ips"]: found_in_active = True
                
                # إذا لم نجد الـ IP في حالة "تجاوز" حالية، نفك حظره
                if not found_in_active or any(len(d["ips"]) <= d["limit"] for d in user_data.values()):
                    os.system(f"iptables -D INPUT -s {b_ip} -j DROP")
                    blocked_ips.discard(b_ip)
                    print(f"✅ فك الحظر عن: {b_ip} لتوافر مكان.")

        except: pass
        time.sleep(2)

if __name__ == '__main__':
    enforce_limit()
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
Description=V2Ray IP Monitor Dynamic
After=network.target
[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/monitor.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# 10. التشغيل النهائي وتنظيف قواعد الجدار الناري القديمة
iptables -F
systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl start v2ray-bot v2ray-monitor

echo "✅ تم التحديث بنجاح!"
echo "📡 نظام المراقبة الجديد يراقب بورت 80 مباشرة."
