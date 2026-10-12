#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]]
role=$(cat /etc/Home_server-role)
apt-get install -y conntrack
install -d -m 0755 /etc/systemd/journald.conf.d
printf '[Journal]\nForwardToSyslog=yes\n' > /etc/systemd/journald.conf.d/20-Home_server.conf
systemctl restart systemd-journald
if [[ $role != host ]]; then
 cat > /etc/systemd/system/Home_server-docker-events.service <<'EOF'
[Unit]
Description=Home_server evenements Docker
After=docker.service
Requires=docker.service
[Service]
ExecStart=/usr/bin/docker events --format {{json .}}
Restart=always
RestartSec=2
SyslogIdentifier=Home_server-DOCKER
[Install]
WantedBy=multi-user.target
EOF
 systemctl daemon-reload
 systemctl enable --now Home_server-docker-events.service
fi
cat > /etc/systemd/system/Home_server-flux.service <<'EOF'
[Unit]
Description=Home_server suivi des connexions reseau
After=network-online.target
[Service]
ExecStart=/usr/sbin/conntrack -E -o timestamp,extended
Restart=always
RestartSec=2
SyslogIdentifier=Home_server-NETFLOW
StandardOutput=journal
StandardError=journal
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
rsyslogd -N1
systemctl restart rsyslog prometheus-node-exporter
systemctl enable --now Home_server-flux.service Home_server-etat.timer
if [[ $role == services ]]; then
 for f in brut.log evenements.jsonl; do
  [[ -e /var/log/Home_server/$f ]] || install -m 0640 -o syslog -g adm /dev/null /var/log/Home_server/$f
 done
 # Resolve official Docker images once, store digests. No SMTP required by Grafana.
 envfile=/opt/Home_server-monitoring/.env
 if grep -q A_RENSEIGNER_DIGEST "$envfile"; then
  for pair in 'IMAGE_LOKI grafana/loki:latest' 'IMAGE_PROMETHEUS prom/prometheus:latest' 'IMAGE_GRAFANA grafana/grafana:latest' 'IMAGE_ALLOY grafana/alloy:latest'; do
   read -r var img <<< "$pair"
   docker pull "$img"
   digest=$(docker image inspect "$img" --format '{{index .RepoDigests 0}}')
   sed -i "s|^$var=.*|$var=$digest|" "$envfile"
  done
  secret=$(openssl rand -hex 20)
  sed -i "s/^GRAFANA_ADMIN_PASSWORD=.*/GRAFANA_ADMIN_PASSWORD=$secret/" "$envfile"
  echo 'Mot de passe initial Grafana enregistre dans /opt/Home_server-monitoring/.env ; consulter localement avec sudo nano.'
 fi
 docker compose -f /opt/Home_server-monitoring/compose.yaml config --quiet
 docker compose -f /opt/Home_server-monitoring/compose.yaml up -d
 if python3 -c 'import json; c=json.load(open("/etc/Home_server-mail/config.json")); assert c["password"]!="SECRET_LOCAL"'; then
  systemctl enable --now Home_server-mail.timer
 else
  echo 'Alertes mail non configurees. Utiliser scripts/mail.py.'
 fi
fi
