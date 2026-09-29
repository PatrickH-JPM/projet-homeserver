#!/bin/bash
# Fichier: generate-certs.sh
# Emplacement: Project_homeserver/NAS/reverse-proxy/generate-certs.sh
# Langage: Bash (openssl)
# Role: cree une autorite de certification (CA) locale puis un certificat SSL signe par
#       cette CA pour le Panel et Grafana, afin d'avoir du HTTPS valide en interne
#       sans dependre d'un nom de domaine public ni de Let's Encrypt.

#!/usr/bin/env bash
set -euo pipefail
CERT_DIR="./certs"
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

# 1. Autorité de certification locale
openssl genrsa -out homeserver-ca.key 4096
openssl req -x509 -new -nodes \
  -key homeserver-ca.key \
  -sha256 -days 3650 \
  -subj "/C=FR/O=Homeserver/CN=Homeserver Root CA" \
  -out homeserver-ca.crt
  
# 2. Fichier de config listant les trois noms couverts
cat > server.cnf <<'EOF'
[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
req_extensions     = req_ext
distinguished_name = dn
[dn]
C  = FR
O  = Homeserver
CN = panel.homeserver.local
[req_ext]
subjectAltName = @alt_names
[alt_names]
DNS.1 = panel.homeserver.local
DNS.2 = grafana.homeserver.local
DNS.3 = wings.homeserver.local
IP.1  = 192.168.2.10
EOF

# 3. Clé et CSR du certificat serveur
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -config server.cnf

# 4. Signature par la CA locale
openssl x509 -req \
  -in server.csr \
  -CA homeserver-ca.crt -CAkey homeserver-ca.key -CAcreateserial \
  -out server.crt -days 825 -sha256 \
  -extensions req_ext -extfile server.cnf
echo "Certificats generes dans $CERT_DIR :"
ls -l homeserver-ca.crt server.crt server.key