#!/bin/bash

# 1. تثبيت الأدوات الضرورية (أضفنا lsof و netstat)
apt update && apt install python3-pip python3-venv curl jq ufw net-tools conntrack lsof -y
ufw allow 80/tcp
ufw --force enable

# 2. إعدادات Xray (مهم جداً: تفعيل الـ Access Log في ملف خارجي)
mkdir -p /var/log/xray
mkdir -p /usr/local/etc/xray
cat <<EOF > /usr/local/etc/xray/config.json
{
    "log": {
        "access": "/var/log/xray/access.log",
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
    "outbounds": [{"protocol": "freedom"}]
}
EOF
touch /var/log/xray/access.log
chmod 666 /var/log/xray/access.log
systemctl restart xray

# 3. سكريبت المراقبة (monitor.py) - النسخة "اللحظية"
cat <<EOF > /etc/my-v2ray/monitor.py
import os, time, subprocess

def enforce_limit():
    print("نظام الحظر الفولاذي يعمل الآن...")
    blocked_ips = {} # {ip: timestamp}

    while True:
        # قراءة آخر 50 سطر من ملف السجل مباشرة (أسرع من journalctl)
        try:
            with open("/var/log/xray/access.log", "r") as f:
                lines = f.readlines()[-50:]
            
            user_ips = {} # {email: set(ips)}
            user_limits = {} # {email: int}

            for line in lines:
                if "accepted" in line and "email: limit_" in line:
                    parts = line.split("email: limit_")[1]
                    limit = int(parts.split("_")[0])
                    email = "limit_" + parts.split()[0]
                    ip = line.split("from:")[1].split(":")[0].strip()
                    
                    if email not in user_ips:
                        user_ips[email] = set()
                        user_limits[email] = limit
                    user_ips[email].add(ip)

            # الحظر اللحظي
            for email, ips in user_ips.items():
                limit = user_limits[email]
                active_ips = list(ips)
                
                if limit == 0 or len(active_ips) > limit:
                    # إذا كان الحد 0 احظر الكل، وإذا زاد احظر الزائد
                    to_block = active_ips if limit == 0 else active_ips[limit:]
                    for target in to_block:
                        if target not in blocked_ips:
                            # حظر في الجدار الناري + قطع الجلسة فوراً
                            os.system(f"iptables -I INPUT -p tcp -s {target} --dport 80 -j DROP")
                            os.system(f"conntrack -D -s {target} > /dev/null 2>&1")
                            blocked_ips[target] = time.time()
                            print(f"🚫 سحق اتصال مخالف: {target} للمستخدم {email}")

            # فك الحظر التلقائي بعد 30 ثانية لتجربة حالة المستخدم (إذا أغلق جهازه)
            now = time.time()
            for ip, t in list(blocked_ips.items()):
                if now - t > 30:
                    os.system(f"iptables -D INPUT -p tcp -s {ip} --dport 80 -j DROP")
                    del blocked_ips[ip]

        except Exception as e:
            pass
        
        time.sleep(0.5) # فحص كل نصف ثانية (سرعة خارقة)

if __name__ == '__main__':
    enforce_limit()
EOF

# 4. تشغيل الخدمات وتصفير القواعد
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

iptables -F
systemctl daemon-reload
systemctl enable v2ray-monitor
systemctl restart v2ray-monitor
