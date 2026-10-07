#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]]
role=$(cat /etc/Home_server-role)
systemctl daemon-reload
systemctl enable --now Home_server-firewall.service
if [[ $role == services ]]; then
 nginx -t
 systemctl enable --now mariadb redis-server php8.3-fpm nginx pteroq
else
 [[ -s /etc/pterodactyl/config.yml && -s /etc/Home_server-pki/wings.key ]]
 systemctl enable --now wings
fi
