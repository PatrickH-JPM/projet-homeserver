#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 && $(cat /etc/Home_server-role) == game ]]
archive=${1:?chemin archive requis}
install -d -m 0700 /etc/Home_server-pki
cd /etc/Home_server-pki
tar -xf "$archive" --no-same-owner wings.key wings.crt ca.crt
chown root:root wings.key wings.crt ca.crt
chmod 0600 wings.key
chmod 0644 wings.crt ca.crt
install -m 0644 ca.crt /usr/local/share/ca-certificates/Home_server.crt
update-ca-certificates
