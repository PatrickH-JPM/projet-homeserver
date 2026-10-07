#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 && $(cat /etc/Home_server-role) != host ]]
[[ ! -e /etc/Home_server-deploiement/crowdsec-configure ]] || { echo 'CrowdSec deja configure.'; exit 0; }
curl --proto '=https' --tlsv1.2 -fsSL https://install.crowdsec.net -o /etc/Home_server-deploiement/crowdsec-repository.sh
sh /etc/Home_server-deploiement/crowdsec-repository.sh
# No generated firewall rules before set-only configuration.
systemctl mask --runtime crowdsec-firewall-bouncer.service
apt-get update
apt-get install -y crowdsec crowdsec-firewall-bouncer-iptables
systemctl stop crowdsec
python3 - <<'PY'
from pathlib import Path
import yaml
p=Path('/etc/crowdsec/config.yaml');c=yaml.safe_load(p.read_text());c['api']['server']['listen_uri']='127.0.0.1:8081';p.write_text(yaml.safe_dump(c,sort_keys=False))
p=Path('/etc/crowdsec/local_api_credentials.yaml');c=yaml.safe_load(p.read_text());c['url']='http://127.0.0.1:8081/';p.write_text(yaml.safe_dump(c,sort_keys=False));p.chmod(0o600)
PY
cscli collections install crowdsecurity/sshd
if [[ $(cat /etc/Home_server-role) == services ]]; then cscli collections install crowdsecurity/nginx; fi
systemctl restart crowdsec
secret=$(cscli bouncers add Home_server-firewall -o raw)
install -d -m 0700 /etc/crowdsec/bouncers
cat > /etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml <<EOF
mode: ipset
api_url: http://127.0.0.1:8081/
api_key: $secret
blacklists_ipv4: cs-Home_server-v4
disable_ipv6: true
update_frequency: 2s
log_mode: file
log_dir: /var/log/
log_level: info
EOF
chmod 0600 /etc/crowdsec/bouncers/crowdsec-firewall-bouncer.yaml
/usr/local/sbin/Home_server-firewall
systemctl unmask crowdsec-firewall-bouncer.service
systemctl daemon-reload
systemctl enable --now crowdsec crowdsec-firewall-bouncer
touch /etc/Home_server-deploiement/crowdsec-configure
