#!/bin/bash
# Fichier: install-crowdsec.sh
# Emplacement: Project_homeserver/serveur/crowdsec/install-crowdsec.sh
# Langage: Bash
# Role: installe CrowdSec et ses collections de detection (SSH, pare-feu Linux)
#       sur la machine serveur, puis active le bouncer local qui bannit reellement les IP.
set -e
echo ">>> Installation du depot officiel CrowdSec"
curl -s https://install.crowdsec.net | sudo sh
echo ">>> Installation du paquet CrowdSec"
sudo apt install -y crowdsec
echo ">>> Installation des collections de detection"
sudo cscli collections install crowdsecurity/sshd
sudo cscli collections install crowdsecurity/linux
echo ">>> Installation du bouncer firewall (applique reellement les bans via nftables/iptables)"
sudo apt install -y crowdsec-firewall-bouncer-iptables
echo ">>> Copie du fichier acquis.yaml prepare a l'avance"
sudo cp ./acquis.yaml /etc/crowdsec/acquis.yaml
echo ">>> Redemarrage de CrowdSec pour prendre en compte la config"
sudo systemctl restart crowdsec
echo ">>> Verification du statut"
sudo systemctl status crowdsec --no-pager
sudo cscli collections list