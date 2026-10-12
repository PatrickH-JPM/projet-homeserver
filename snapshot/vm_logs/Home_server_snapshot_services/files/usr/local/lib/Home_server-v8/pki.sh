#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 && $(cat /etc/Home_server-role) == services ]]
[[ ! -e /etc/Home_server-pki/services.key ]] || { echo 'Certificats deja presents. Renouvellement manuel requis.'; exit 1; }
install -d -m 0700 /root/Home_server-pki
cd /root/Home_server-pki
umask 077
openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 -keyout ca.key -out ca.crt -subj '/CN=Home_server CA' -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign'
for name in services wings; do
 if [[ $name == services ]]; then san='DNS:panel.home.arpa,DNS:grafana.home.arpa,DNS:wings.home.arpa,IP:192.168.5.10'; else san='DNS:wings-game.home.arpa,IP:192.168.4.10'; fi
 openssl req -new -newkey rsa:3072 -nodes -keyout "$name.key" -out "$name.csr" -subj "/CN=Home_server-$name"
 printf 'subjectAltName=%s\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n' "$san" > "$name.ext"
 openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -out "$name.crt" -days 365 -sha256 -extfile "$name.ext"
done
install -m 0600 services.key /etc/Home_server-pki/services.key
install -m 0644 services.crt /etc/Home_server-pki/services.crt
install -m 0644 ca.crt /etc/Home_server-pki/services-ca.crt
install -m 0644 ca.crt /usr/local/share/ca-certificates/Home_server.crt
update-ca-certificates
# Bundle carries only guest terminal key, never CA key; remove after transfer.
tar -cf /home/patrick/Home_server-wings-tls.tar wings.key wings.crt ca.crt
chown patrick:patrick /home/patrick/Home_server-wings-tls.tar
chmod 0600 /home/patrick/Home_server-wings-tls.tar
install -m 0644 ca.crt /home/patrick/Home_server-ca.crt
tar -cf /home/patrick/Home_server-ca-private.tar ca.key ca.crt
chown patrick:patrick /home/patrick/Home_server-ca-private.tar
chmod 0600 /home/patrick/Home_server-ca-private.tar
echo 'Certificats crees. Transferer le paquet Wings et la CA publique comme indique dans le guide.'
