#!/bin/bash

# 1. تثبيت الأدوات الأساسية
apt update && apt install python3-pip python3-venv curl jq ufw net-tools conntrack lsof socat -y
ufw allow 22/tcp
# سنفتح كل المنافذ المتوقعة، لكن الأدمن هو من يحدد لاحقاً
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 1000:65000/tcp
ufw --force enable

# 2. إعداد Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

mkdir -p /var/log/xray
mkdir -p /usr/local/etc/xray

# 3. إنشاء ملف Config أساسي (يحتوي فقط على الـ API Stats)
# المداخل (Inbounds) ستضاف تلقائياً عن طريق البوت
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": { "access": "/var/log/xray/access.log", "loglevel": "warning" },
    "stats": {},
    "api": { "tag": "api", "services": ["StatsService"] },
    "policy": {
        "levels": { "0": { "statsUserUplink": true, "statsUserDownlink": true } },
        "system": { "statsInboundUplink": true, "statsInboundDownlink": true }
    },
    "inbounds": [
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

# 4. إعداد بيئة البوت
pip install python-telegram-bot --upgrade --break-system-packages

read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID) الخاص بك: " MY_ID
mkdir -p /etc/my-v2ray

echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

# ملفات قاعدة البيانات الفارغة
echo "{}" > /etc/my-v2ray/products.json
echo "{\"$MY_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# تحميل ملفات البوت (سيتم وضع الأكواد الجديدة بالأسفل)
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"

# 5. سكريبت المراقبة
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess, json

def get_stats():
    try:
        cmd = "xray api statsquery --server=127.0.0.1:10085"
        output = subprocess.check_output(cmd, shell=True).decode()
        return json.loads(output)
    except: return None

def save_config(config):
    with open("/usr/local/etc/xray/config.json", 'w') as f:
        json.dump(config, f, indent=4)
    os.system("systemctl restart xray")

def enforce_rules():
    print("🛡️ الحارس يعمل على جميع البروتوكولات...")
    while True:
        try:
            stats = get_stats()
            # قراءة ملف الكونفج للبحث عن المستخدمين
            with open("/usr/local/etc/xray/config.json", 'r') as f:
                config = json.load(f)
            
            # خريطة الاستهلاك {email: bytes}
            usage_map = {}
            if stats and 'stat' in stats:
                for s in stats['stat']:
                    if 'user>>>' in s['name']:
                        email = s['name'].split('>>>')[1]
                        usage_map[email] = usage_map.get(email, 0) + int(s['value'])
            
            current_time = int(time.time())
            config_changed = False

            # فحص كل المداخل (Inbounds)
            for inbound in config['inbounds']:
                # التعامل مع البروتوكولات المختلفة
                clients = []
                if inbound['protocol'] in ['vless', 'vmess', 'trojan']:
                    if 'clients' in inbound['settings']:
                        clients = inbound['settings']['clients']
                elif inbound['protocol'] == 'shadowsocks':
                    if 'users' in inbound['settings']:
                        clients = inbound['settings']['users']
                
                # قائمة للحذف
                to_remove = []
                
                for client in clients:
                    # في Shadowsocks أحياناً يكون password بدلاً من id
                    email = client.get('email', '')
                    if not email or 'limit_' not in email: continue

                    try:
                        # تحليل الإيميل: limit_X_max_Y_exp_Z_uuid
                        parts = email.split('_')
                        max_idx = parts.index('max') + 1
                        exp_idx = parts.index('exp') + 1
                        
                        max_bytes = int(parts[max_idx])
                        exp_time = int(parts[exp_idx])
                        
                        # 1. فحص الوقت
                        if current_time > exp_time:
                            print(f"⏰ انتهاء وقت: {email}")
                            to_remove.append(client)
                            continue
                        
                        # 2. فحص السعة
                        used = usage_map.get(email, 0)
                        if used >= max_bytes:
                            print(f"💾 انتهاء سعة: {email}")
                            to_remove.append(client)
                            continue

                    except: continue
                
                # تنفيذ الحذف
                if to_remove:
                    for r in to_remove:
                        clients.remove(r)
                    config_changed = True

            if config_changed:
                save_config(config)

        except Exception as e:
            print(f"Error: {e}")
        
        time.sleep(10)

if __name__ == '__main__':
    enforce_rules()
EOF

# 6. الخدمات
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray Super Bot
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
