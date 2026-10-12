#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]]
role=$(cat /etc/Home_server-role)
apt-get install -y conntrack
install -d -m 0755 /etc/systemd/journald.conf.d
printf '[Journal]\nForwardToSyslog=yes\n' > /etc/systemd/journald.conf.d/20-Home_server.conf
systemctl restart systemd-journald
if [[ $role != host ]]; then
 cat > /etc/systemd/system/Home_server-docker-events.service <<'UNIT'
[Unit]
Description=Home_server evenements Docker
After=docker.service
Requires=docker.service
[Service]
ExecStart=/usr/bin/docker events "--format={{json .}}"
Restart=always
RestartSec=2
SyslogIdentifier=Home_server-DOCKER
[Install]
WantedBy=multi-user.target
UNIT
 systemctl daemon-reload
 systemctl enable --now Home_server-docker-events.service
fi
cat > /etc/systemd/system/Home_server-flux.service <<'UNIT'
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
UNIT
systemctl daemon-reload
rsyslogd -N1
systemctl restart rsyslog prometheus-node-exporter
systemctl enable --now Home_server-flux.service Home_server-etat.timer Home_server-conntrack.timer
if [[ $role == services ]]; then
 systemctl enable --now Home_server-er605-snmp.timer
 docker compose -f /opt/Home_server-monitoring/compose.yaml config --quiet
 docker compose -f /opt/Home_server-monitoring/compose.yaml up -d
fi
