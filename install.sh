#!/bin/bash

# 1. تثبيت المتطلبات الأساسية وأدوات الشبكة
apt update && apt install python3-pip python3-venv curl jq ufw net-tools conntrack lsof -y
ufw allow 80/tcp
ufw allow 10085/tcp
ufw --force enable

# 2. إيقاف تعارض نظام الأسماء (DNS) في Ubuntu 24
systemctl stop systemd-resolved
systemctl disable systemd-resolved
echo "nameserver 8.8.8.8" > /etc/resolv.conf

# 3. تثبيت محرك Xray الرسمي
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

# 4. إنشاء ملف إعدادات Xray نظيف ويدعم الإحصائيات (النسخة الآمنة)
mkdir -p /var/log/xray
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
    "outbounds": [{ "protocol": "freedom" }],
    "routing": { "rules": [{ "inboundTag": ["api"], "outboundTag": "api", "type": "field" }] }
}
EOF

touch /var/log/xray/access.log
chmod 666 /var/log/xray/access.log
systemctl restart xray

# 5. تثبيت مكتبة التليجرام
pip install python-telegram-bot --upgrade --break-system-packages

# 6. طلب بيانات البوت من المدير
read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# 7. تحميل ملف البوت (core.py)
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 8. إنشاء سكريبت المراقبة الذكي (monitor.py) - النسخة الآمنة من تخريب الـ JSON
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess, json

def get_stats():
    try:
        cmd = "xray api statsquery --server=127.0.0.1:10085"
        output = subprocess.check_output(cmd, shell=True).decode()
        return json.loads(output)
    except: return None

def remove_user_safe(email_to_remove):
    config_path = "/usr/local/etc/xray/config.json"
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # تصفية المستخدمين برمجياً لضمان سلامة الملف
        clients = config['inbounds'][0]['settings']['clients']
        new_clients = [c for c in clients if c.get('email') != email_to_remove]
        
        if len(clients) != len(new_clients):
            config['inbounds'][0]['settings']['clients'] = new_clients
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            return True
    except Exception as e:
        print(f"Error safe-updating config: {e}")
    return False

def enforce_all():
    print("المراقب الذكي يعمل بنظام الحماية من تخريب البيانات...")
    blocked_ips = {}

    while True:
        # أولاً: فحص سعة البيانات (الجيجات)
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
                        max_limit = int(email.split('max_')[1].split('_')[0])
                        if used_bytes >= max_limit:
                            print(f"🔥 سحق مستخدم (انتهت السعة): {email}")
                            if remove_user_safe(email):
                                os.system("systemctl restart xray")
                    except: pass

        # ثانياً: فحص عدد الأجهزة (اللحظي) عبر السجل
        try:
            with open("/var/log/xray/access.log", "r") as f:
                lines = f.readlines()[-50:]
            
            active_data = {} # {email: set(ips)}
            for line in lines:
                if "accepted" in line and "email: limit_" in line:
                    parts = line.split("email: limit_")[1]
                    limit = int(parts.split("_")[0])
                    email = "limit_" + parts.split()[0]
                    ip = line.split("from:")[1].split(":")[0].strip()
                    
                    if email not in active_data: active_data[email] = {"limit": limit, "ips": set()}
                    active_data[email]["ips"].add(ip)

            for email, data in active_data.items():
                ips = list(data["ips"])
                if data["limit"] == 0 or len(ips) > data["limit"]:
                    target_ips = ips if data["limit"] == 0 else ips[data["limit"]:]
                    for tip in target_ips:
                        if tip not in blocked_ips:
                            os.system(f"iptables -I INPUT -p tcp -s {tip} --dport 80 -j DROP")
                            os.system(f"conntrack -D -s {tip} > /dev/null 2>&1")
                            blocked_ips[tip] = time.time()
        except: pass
        
        # تنظيف الجدار الناري مؤقتاً كل 30 ثانية
        now = time.time()
        for ip, t in list(blocked_ips.items()):
            if now - t > 30:
                os.system(f"iptables -D INPUT -p tcp -s {ip} --dport 80 -j DROP")
                del blocked_ips[ip]

        time.sleep(5)

if __name__ == '__main__':
    enforce_all()
EOF

# 9. إعداد خدمات النظام
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

# 10. التشغيل النهائي
iptables -F
systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl restart v2ray-bot v2ray-monitor

echo "✅ تم الإصلاح والتحديث بنظام الحذف الآمن!"
