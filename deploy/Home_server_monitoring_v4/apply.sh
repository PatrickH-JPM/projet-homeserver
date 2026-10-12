#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Lancer avec sudo.' >&2; exit 1; }
ROOT=$(cd "$(dirname "$0")" && pwd)
ROLE=$(cat /etc/Home_server-role)
case "$ROLE" in host|game|services) ;; *) echo "Role inconnu: $ROLE" >&2; exit 1;; esac
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="/root/Home_server-monitoring-backup-$STAMP"
mkdir -p "$BACKUP"

echo "[1/7] Sauvegarde -> $BACKUP"
for f in \
 /usr/local/sbin/Home_server-etat.py \
 /usr/local/sbin/Home_server-conntrack.py \
 /etc/systemd/system/Home_server-etat.service \
 /etc/systemd/system/Home_server-etat.timer \
 /etc/systemd/system/Home_server-conntrack.service \
 /etc/systemd/system/Home_server-conntrack.timer; do
  [[ -e "$f" ]] && cp -a --parents "$f" "$BACKUP/"
done
if [[ $ROLE == services ]]; then
  for f in /opt/Home_server-monitoring/prometheus.yaml /opt/Home_server-monitoring/compose.yaml \
           /opt/Home_server-monitoring/dashboards/systemes.json \
           /opt/Home_server-monitoring/dashboards/reseau.json \
           /opt/Home_server-monitoring/dashboards/minecraft.json \
           /usr/local/sbin/Home_server-firewall \`n           /usr/local/sbin/Home_server-er605-snmp.py \
           /etc/systemd/system/Home_server-er605-snmp.service \
           /etc/systemd/system/Home_server-er605-snmp.timer; do
    [[ -e "$f" ]] && cp -a --parents "$f" "$BACKUP/"
  done
fi

echo '[2/7] Installation collecteurs communs'
install -d -m 0755 /var/lib/Home_server-textfile
install -d -m 0700 /var/lib/Home_server-state
install -m 0750 "$ROOT/common/usr/local/sbin/Home_server-etat.py" /usr/local/sbin/Home_server-etat.py
install -m 0750 "$ROOT/common/usr/local/sbin/Home_server-conntrack.py" /usr/local/sbin/Home_server-conntrack.py
install -m 0644 "$ROOT/common/etc/systemd/system/Home_server-etat.service" /etc/systemd/system/Home_server-etat.service
install -m 0644 "$ROOT/common/etc/systemd/system/Home_server-etat.timer" /etc/systemd/system/Home_server-etat.timer
install -m 0644 "$ROOT/common/etc/systemd/system/Home_server-conntrack.service" /etc/systemd/system/Home_server-conntrack.service
install -m 0644 "$ROOT/common/etc/systemd/system/Home_server-conntrack.timer" /etc/systemd/system/Home_server-conntrack.timer

echo '[3/7] Validation Python'
python3 -m py_compile /usr/local/sbin/Home_server-etat.py /usr/local/sbin/Home_server-conntrack.py

if [[ $ROLE == services ]]; then
  echo '[4/7] Installation collecteur ER605 + monitoring services'
  command -v snmpget >/dev/null 2>&1 || apt-get install -y snmp
  install -m 0750 "$ROOT/services/usr/local/sbin/Home_server-firewall" /usr/local/sbin/Home_server-firewall
  install -m 0750 "$ROOT/services/usr/local/sbin/Home_server-er605-snmp.py" /usr/local/sbin/Home_server-er605-snmp.py
  install -m 0644 "$ROOT/services/etc/systemd/system/Home_server-er605-snmp.service" /etc/systemd/system/Home_server-er605-snmp.service
  install -m 0644 "$ROOT/services/etc/systemd/system/Home_server-er605-snmp.timer" /etc/systemd/system/Home_server-er605-snmp.timer
  if [[ ! -e /etc/Home_server-er605-snmp.json ]]; then
    install -m 0600 "$ROOT/services/etc/Home_server-er605-snmp.json.example" /etc/Home_server-er605-snmp.json
  fi
  python3 -m py_compile /usr/local/sbin/Home_server-er605-snmp.py
  install -m 0644 "$ROOT/services/opt/Home_server-monitoring/prometheus.yaml" /opt/Home_server-monitoring/prometheus.yaml
  install -m 0644 "$ROOT/services/opt/Home_server-monitoring/compose.yaml" /opt/Home_server-monitoring/compose.yaml
  install -m 0644 "$ROOT/services/opt/Home_server-monitoring/dashboards/systemes.json" /opt/Home_server-monitoring/dashboards/systemes.json
  install -m 0644 "$ROOT/services/opt/Home_server-monitoring/dashboards/reseau.json" /opt/Home_server-monitoring/dashboards/reseau.json
  install -m 0644 "$ROOT/services/opt/Home_server-monitoring/dashboards/minecraft.json" /opt/Home_server-monitoring/dashboards/minecraft.json
  python3 -m json.tool /opt/Home_server-monitoring/dashboards/systemes.json >/dev/null
  python3 -m json.tool /opt/Home_server-monitoring/dashboards/reseau.json >/dev/null
  python3 -m json.tool /opt/Home_server-monitoring/dashboards/minecraft.json >/dev/null
fi

if [[ $ROLE == game ]]; then
  install -m 0750 "$ROOT/game/usr/local/sbin/Home_server-minecraft-console.sh" /usr/local/sbin/Home_server-minecraft-console.sh
  install -m 0644 "$ROOT/game/etc/systemd/system/Home_server-minecraft-console.service" /etc/systemd/system/Home_server-minecraft-console.service
  bash -n /usr/local/sbin/Home_server-minecraft-console.sh
fi

echo '[5/7] systemd'
systemctl daemon-reload
systemctl enable --now Home_server-etat.timer Home_server-conntrack.timer
systemctl restart Home_server-etat.timer Home_server-conntrack.timer
if [[ $ROLE == services ]]; then
  /usr/local/sbin/Home_server-firewall
  systemctl enable --now Home_server-er605-snmp.timer
  systemctl restart Home_server-er605-snmp.timer
fi

if [[ $ROLE == game ]]; then
  systemctl enable --now Home_server-minecraft-console.service
  systemctl restart Home_server-minecraft-console.service
fi

echo '[6/7] PremiÃƒÂ¨re collecte'
systemctl start Home_server-etat.service
systemctl start Home_server-conntrack.service
if [[ $ROLE == services ]]; then systemctl start Home_server-er605-snmp.service || true; fi

if [[ $ROLE == services ]]; then
  echo '[7/7] Rechargement Prometheus/Grafana'
  docker compose -f /opt/Home_server-monitoring/compose.yaml config --quiet
  docker compose -f /opt/Home_server-monitoring/compose.yaml up -d prometheus grafana
else
  echo '[7/7] Pas de conteneurs monitoring sur ce rÃƒÂ´le'
fi

echo
printf 'OK role=%s backup=%s\n' "$ROLE" "$BACKUP"
systemctl --no-pager --full status Home_server-etat.timer Home_server-conntrack.timer | sed -n '1,35p' || true
