#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Executer avec sudo sur Home_server_services." >&2; exit 1; }
[[ -f /etc/Home_server-role ]] || { echo "Role Home_server introuvable." >&2; exit 1; }
[[ $(cat /etc/Home_server-role) == services ]] || { echo "Installation V2 uniquement sur Home_server_services." >&2; exit 1; }
[[ -f /var/log/Home_server/brut.log ]] || { echo "/var/log/Home_server/brut.log absent." >&2; exit 1; }
ROOT=$(cd "$(dirname "$0")/.." && pwd)

# Couper l'ancien envoi mail pendant la mise au point V2.
systemctl disable --now Home_server-mail.timer 2>/dev/null || true
systemctl disable --now Home_server-mail-v2.timer 2>/dev/null || true

id Home_serverevents >/dev/null 2>&1 || useradd --system --home-dir /var/lib/Home_server-events-v2 --shell /usr/sbin/nologin Home_serverevents
usermod -aG adm Home_serverevents
install -d -m 0750 -o Home_serverevents -g adm /var/lib/Home_server-events-v2
install -d -m 0750 -o root -g adm /etc/Home_server-events-v2

install -m 0755 "$ROOT/usr/local/sbin/Home_server-events-v2.py" /usr/local/sbin/Home_server-events-v2.py
install -m 0755 "$ROOT/usr/local/bin/Home_server-journal" /usr/local/bin/Home_server-journal
install -m 0755 "$ROOT/usr/local/sbin/Home_server-mail-v2.py" /usr/local/sbin/Home_server-mail-v2.py
install -m 0644 "$ROOT/etc/systemd/system/Home_server-events-v2.service" /etc/systemd/system/Home_server-events-v2.service
install -m 0644 "$ROOT/etc/systemd/system/Home_server-mail-v2.service" /etc/systemd/system/Home_server-mail-v2.service
install -m 0644 "$ROOT/etc/systemd/system/Home_server-mail-v2.timer" /etc/systemd/system/Home_server-mail-v2.timer
install -m 0644 "$ROOT/etc/logrotate.d/Home_server-events-v2" /etc/logrotate.d/Home_server-events-v2

for f in config.json identities.json rules.json mail-policy.json; do
  src="$ROOT/etc/Home_server-events-v2/$f"
  dst="/etc/Home_server-events-v2/$f"
  if [[ -e "$dst" ]]; then
    install -m 0640 -o root -g adm "$src" "$dst.new"
    echo "Conserve: $dst ; nouvelle proposition: $dst.new"
  else
    install -m 0640 -o root -g adm "$src" "$dst"
  fi
done

[[ -e /var/log/Home_server/evenements-v2.jsonl ]] || install -m 0640 -o Home_serverevents -g adm /dev/null /var/log/Home_server/evenements-v2.jsonl
chown Home_serverevents:adm /var/log/Home_server/evenements-v2.jsonl
chmod 0640 /var/log/Home_server/evenements-v2.jsonl

systemctl daemon-reload
systemctl enable --now Home_server-events-v2.service

echo
echo "V2 installee. L'ancien mail reste DESACTIVE."
echo "Affichage live : Home_server-journal"
echo "Etat moteur    : systemctl status Home_server-events-v2 --no-pager"
echo "Politique mail : /etc/Home_server-events-v2/mail-policy.json"
