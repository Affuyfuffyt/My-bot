#!/bin/bash

# 1. تحديث النظام وتثبيت المتطلبات الأساسية
apt update && apt install python3-pip python3-venv curl jq ufw net-tools -y
ufw allow 80/tcp
ufw --force enable

# 2. إيقاف التعارض مع خدمات Ubuntu 24 لضمان عمل بورت 80
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت محرك Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إعداد ملف Xray (VLESS WS Port 80) مع سجلات دقيقة
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

# 5. تحديث مكتبة تليجرام لضمان عمل نظام المحادثة (ConversationHandler)
pip install python-telegram-bot --upgrade --break-system-packages

# 6. إعداد بيانات البوت
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 7. تحميل كود البوت (core.py)
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 8. إنشاء سكريبت المراقبة الذكي (monitor.py) المحدث
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess

def get_realtime_connections():
    try:
        # فحص بورت 80 وجلب الـ IPs المتصلة فعلياً
        cmd = "netstat -tnp | grep ':80 ' | grep 'ESTABLISHED' | awk '{print \$5}' | cut -d: -f1"
        output = subprocess.check_output(cmd, shell=True).decode()
        return [ip.strip() for ip in output.split('\n') if ip.strip()]
    except: return []

def enforce_limit():
    blocked_ips = set()
    print("المراقب الذكي يعمل.. بانتظار الاتصالات..")
    
    while True:
        connections = get_realtime_connections()
        unique_active_ips = set(connections)
        
        # قراءة السجلات لمعرفة المستخدمين وحدودهم
        cmd_logs = "journalctl -u xray --since '10 seconds ago' | grep 'accepted'"
        try:
            logs = subprocess.check_output(cmd_logs, shell=True).decode()
            user_data = {} 
            
            for line in logs.split('\n'):
                if 'email: limit_' in line:
                    try:
                        parts = line.split('email: limit_')[1]
                        limit = int(parts.split('_')[0])
                        email = "limit_" + parts.split()[0]
                        ip = line.split('from:')[1].split(':')[0].strip()
                        
                        if ip in unique_active_ips:
                            if email not in user_data: user_data[email] = {"limit": limit, "ips": set()}
                            user_data[email]["ips"].add(ip)
                    except: continue

            # تطبيق قوانين الحظر
            for email, data in user_data.items():
                active_list = list(data["ips"])
                limit = data["limit"]

                # إذا كان الحد 0 (منع كامل) أو تجاوز العدد المسموح
                if len(active_list) > limit or limit == 0:
                    to_block = active_list if limit == 0 else active_list[limit:]
                    for tip in to_block:
                        if tip not in blocked_ips:
                            os.system(f"iptables -I INPUT -s {tip} -j DROP")
                            blocked_ips.add(tip)
                            print(f"🚫 حظر IP: {tip} (الحد: {limit})")

            # فك الحظر التلقائي عند توفر مكان
            for b_ip in list(blocked_ips):
                still_violating = False
                for email, data in user_data.items():
                    if b_ip in data["ips"] and (len(data["ips"]) > data["limit"] or data["limit"] == 0):
                        still_violating = True
                
                if not still_violating:
                    os.system(f"iptables -D INPUT -s {b_ip} -j DROP")
                    blocked_ips.discard(b_ip)
                    print(f"✅ فك الحظر: {b_ip}")

        except: pass
        time.sleep(2)

if __name__ == '__main__':
    enforce_limit()
EOF

# 9. إعداد خدمات النظام للعمل تلقائياً في الخلفية
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

# 10. تشغيل الخدمات وتنظيف الجدار الناري
iptables -F
systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl start v2ray-bot v2ray-monitor

echo "✅ اكتمل التحديث بنجاح!"
echo "📡 السيرفر يراقب الآن بورت 80 بدقة (حظر كامل إذا كان الحد 0)."
