#!/bin/bash

# 1. التثبيت
apt update && apt install python3-pip python3-venv curl jq ufw net-tools conntrack lsof socat -y

# فتح البورتات
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 1000:65000/tcp
ufw --force enable

# 2. Xray
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install

mkdir -p /var/log/xray
mkdir -p /usr/local/etc/xray

# 3. Config أساسي
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": { "access": "/var/log/xray/access.log", "loglevel": "warning" },
    "api": { "tag": "api", "services": ["StatsService"] },
    "policy": { "levels": { "0": { "statsUserUplink": true, "statsUserDownlink": true } }, "system": { "statsInboundUplink": true, "statsInboundDownlink": true } },
    "inbounds": [
        { "listen": "127.0.0.1", "port": 10085, "protocol": "dokodemo-door", "settings": { "address": "127.0.0.1" }, "tag": "api" }
    ],
    "outbounds": [{ "protocol": "freedom" }],
    "routing": { "rules": [{ "inboundTag": ["api"], "outboundTag": "api", "type": "field" }] }
}
EOF

touch /var/log/xray/access.log
chmod 666 /var/log/xray/access.log
systemctl restart xray

# 4. البوت
pip install python-telegram-bot --upgrade --break-system-packages

read -p "أدخل توكن البوت: " BOT_TOKEN
read -p "أدخل الأيدي (ID) الخاص بك: " MY_ID
mkdir -p /etc/my-v2ray

echo "TOKEN=\"$BOT_TOKEN\"" > /etc/my-v2ray/config.py
echo "ADMIN_ID=$MY_ID" >> /etc/my-v2ray/config.py

echo "{}" > /etc/my-v2ray/products.json
echo "{\"$MY_ID\": {\"points\": 1000000}}" > /etc/my-v2ray/users.json

# تحميل الملفات الجديدة
curl -L -o /etc/my-v2ray/core.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/core.py"
curl -L -o /etc/my-v2ray/monitor.py "https://raw.githubusercontent.com/Affuyfuffyt/My-bot/main/monitor.py"

# خدمة النظام
cat <<EOF > /etc/systemd/system/v2ray-bot.service
[Unit]
Description=V2Ray Pro Bot
After=network.target
[Service]
ExecStart=/usr/bin/python3 /etc/my-v2ray/core.py
Restart=always
[Install]
WantedBy=multi-user.target
EOF

# خدمة المراقبة (مهمة جداً للحذف التلقائي)
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess, json

def get_stats():
    try:
        return json.loads(subprocess.check_output("xray api statsquery --server=127.0.0.1:10085", shell=True).decode())
    except: return None

def save_config(config):
    with open("/usr/local/etc/xray/config.json", 'w') as f: json.dump(config, f, indent=4)
    os.system("systemctl restart xray")

def enforce():
    print("🛡️ Monitor Started...")
    while True:
        try:
            stats = get_stats()
            with open("/usr/local/etc/xray/config.json", 'r') as f: config = json.load(f)
            
            usage = {}
            if stats and 'stat' in stats:
                for s in stats['stat']:
                    if 'user>>>' in s['name']:
                        email = s['name'].split('>>>')[1]
                        usage[email] = usage.get(email, 0) + int(s['value'])
            
            now = int(time.time())
            changed = False

            for ib in config['inbounds']:
                clients = ib.get('settings', {}).get('clients', []) + ib.get('settings', {}).get('users', [])
                to_del = []
                for c in clients:
                    email = c.get('email', '')
                    if 'limit_' not in email: continue
                    try:
                        # email format: limit_DEVICES_max_BYTES_exp_TIME_uuid
                        parts = email.split('_')
                        max_b = int(parts[parts.index('max')+1])
                        exp_t = int(parts[parts.index('exp')+1])
                        
                        if now > exp_t: to_del.append(c); continue
                        if usage.get(email, 0) >= max_b: to_del.append(c); continue
                    except: continue
                
                if to_del:
                    # Remove from both lists to be safe
                    if 'clients' in ib['settings']: 
                        ib['settings']['clients'] = [x for x in ib['settings']['clients'] if x not in to_del]
                    if 'users' in ib['settings']:
                        ib['settings']['users'] = [x for x in ib['settings']['users'] if x not in to_del]
                    changed = True

            if changed: save_config(config)
        except Exception as e: print(e)
        time.sleep(10)

if __name__ == '__main__': enforce()
EOF

cat <<EOF > /etc/systemd/system/v2ray-monitor.service
[Unit]
Description=Monitor
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
