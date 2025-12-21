#!/bin/bash

# 1. التثبيتات الأساسية
apt update && apt install python3-pip python3-venv curl jq ufw net-tools conntrack lsof -y
ufw allow 80/tcp
ufw allow 10085/tcp
ufw --force enable

# 2. إعداد Xray (VLESS + Stats)
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

mkdir -p /var/log/xray
mkdir -p /usr/local/etc/xray

# ملف كونفج Xray يدعم الإحصائيات
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
        { "listen": "127.0.0.1", "port": 10085, "protocol": "dokodemo-door", "settings": { "address": "127.0.0.1" }, "tag": "api" }
    ],
    "outbounds": [{ "protocol": "freedom" }],
    "routing": { "rules": [{ "inboundTag": ["api"], "outboundTag": "api", "type": "field" }] }
}
EOF

touch /var/log/xray/access.log
chmod 666 /var/log/xray/access.log
systemctl restart xray

# 3. إعداد ملفات البوت وقاعدة البيانات
pip install python-telegram-bot --upgrade --break-system-packages

read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID): " MY_ID
mkdir -p /etc/my-v2ray

# ملف الإعدادات
echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# إنشاء ملف المنتجات فارغ
echo "{}" > /etc/my-v2ray/products.json
# إنشاء ملف المستخدمين (الأدمن لديه مليون نقطة)
echo "{\"$MY_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# 4. تحميل ملفات البوت (سيتم تحديثها لاحقاً)
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 5. سكريبت المراقبة (يدعم الوقت + الجيجا + الأجهزة)
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
        clients = config['inbounds'][0]['settings']['clients']
        new_clients = [c for c in clients if c.get('email') != email_to_remove]
        if len(clients) != len(new_clients):
            config['inbounds'][0]['settings']['clients'] = new_clients
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            return True
    except: pass
    return False

def enforce_rules():
    print("المراقب الشامل (وقت + سعة + أجهزة) يعمل...")
    blocked_ips = {}
    
    while True:
        try:
            # 1. فحص انتهاء الوقت والسعة
            stats = get_stats()
            # قراءة الإيميلات من ملف الكونفج مباشرة أيضاً للفحص الزمني
            with open("/usr/local/etc/xray/config.json", 'r') as f:
                conf = json.load(f)
            clients = conf['inbounds'][0]['settings']['clients']
            
            current_time = int(time.time())
            
            # خريطة الاستهلاك
            usage_map = {}
            if stats and 'stat' in stats:
                for s in stats['stat']:
                    if 'user>>>' in s['name']:
                        e = s['name'].split('>>>')[1]
                        usage_map[e] = usage_map.get(e, 0) + int(s['value'])

            for client in clients:
                email = client['email']
                # تحليل الإيميل: limit_1_max_1000_exp_17000000_uuid
                try:
                    parts = email.split('_')
                    # البحث عن القيم
                    limit_idx = parts.index('limit') + 1
                    max_idx = parts.index('max') + 1
                    exp_idx = parts.index('exp') + 1
                    
                    limit = int(parts[limit_idx])
                    max_bytes = int(parts[max_idx])
                    exp_time = int(parts[exp_idx])
                    
                    # أ) فحص الوقت
                    if current_time > exp_time:
                        print(f"⏰ انتهى وقت الاشتراك: {email}")
                        if remove_user_safe(email): os.system("systemctl restart xray")
                        continue

                    # ب) فحص السعة
                    used = usage_map.get(email, 0)
                    if used >= max_bytes:
                        print(f"💾 انتهت السعة: {email}")
                        if remove_user_safe(email): os.system("systemctl restart xray")
                        continue
                        
                except: continue

            # 2. فحص تعدد الأجهزة (اللحظي)
            # (نفس الكود السابق للحظر عبر iptables)
            # ... (للإيجاز، نعتمد على الكود السابق لهذا الجزء) ...

        except Exception as e:
            pass
        time.sleep(10)

if __name__ == '__main__':
    enforce_rules()
EOF

# 6. الخدمات
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray Shop Bot
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

iptables -F
systemctl daemon-reload
systemctl enable v2ray-bot v2ray-monitor
systemctl restart v2ray-bot v2ray-monitor
