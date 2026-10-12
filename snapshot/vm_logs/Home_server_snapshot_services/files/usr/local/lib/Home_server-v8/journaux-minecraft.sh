#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 && "$(cat /etc/Home_server-role)" == game ]]
UUID=${1:?UUID reel du serveur requis}
[[ "$UUID" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]
DIR="/var/lib/pterodactyl/volumes/$UUID/logs"
[[ -d "$DIR" && -f "$DIR/latest.log" ]]
for p in /var/lib/pterodactyl /var/lib/pterodactyl/volumes "/var/lib/pterodactyl/volumes/$UUID"; do
  setfacl -m u:syslog:--x "$p"
done
setfacl -m u:syslog:r-x,d:u:syslog:r-x "$DIR"
setfacl -m u:syslog:r-- "$DIR/latest.log"
cat > /etc/rsyslog.d/26-Home_server-minecraft.conf <<EOF
input(type="imfile" File="$DIR/latest.log" Tag="mc-serveur:" Severity="info" Facility="local6" PersistStateInterval="100")
EOF
rsyslogd -N1
systemctl restart rsyslog
echo 'Lecture des journaux configuree ; verifier apres rotation Minecraft.'
