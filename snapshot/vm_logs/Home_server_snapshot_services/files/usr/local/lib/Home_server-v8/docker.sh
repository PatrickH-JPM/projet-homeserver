#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 && $(cat /etc/Home_server-role) != host ]]
source /etc/os-release
[[ $VERSION_ID == 24.04 ]]
# Prevent first boot before firewall. Does not alter an already running Docker.
if ! command -v docker >/dev/null; then
 systemctl mask docker.service docker.socket
 apt-get install -y ca-certificates curl
 install -d -m 0755 /etc/apt/keyrings
 curl --proto '=https' --tlsv1.2 -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
 chmod 0644 /etc/apt/keyrings/docker.asc
 cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
EOF
 apt-get update
 apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
 systemctl unmask docker.service docker.socket
fi
systemctl daemon-reload
systemctl enable --now Home_server-firewall.service
systemctl enable --now docker
