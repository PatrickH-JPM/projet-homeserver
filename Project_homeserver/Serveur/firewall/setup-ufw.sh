#!/bin/bash
# Fichier: setup-ufw.sh
# Emplacement: Project_homeserver/serveur/firewall/setup-ufw.sh
# Langage: Bash
# Role: configure ufw sur la machine serveur - bloque tout par defaut (entrant ET sortant),
#       puis n'autorise explicitement que les flux necessaires au fonctionnement du serveur.

#!/usr/bin/env bash
set -euo pipefail
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default deny outgoing
# Sortant indispensable
sudo ufw allow out 53/udp
sudo ufw allow out 53/tcp
sudo ufw allow out 80/tcp
sudo ufw allow out 443/tcp
sudo ufw allow out 123/udp
# Sortant vers le NAS
sudo ufw allow out to 192.168.2.10 port 1514 proto udp
sudo ufw allow out to 192.168.2.10 port 443 proto tcp
# Entrant public - jeu uniquement
sudo ufw allow 49150/tcp
sudo ufw allow 49150/udp
# Entrant - administration via VPN uniquement
sudo ufw allow from 10.10.10.0/24 to any port 22 proto tcp
sudo ufw allow from 10.10.10.0/24 to any port 2022 proto tcp
# Entrant - API Wings, uniquement depuis le NAS
sudo ufw allow from 192.168.2.10 to any port 8080 proto tcp
sudo ufw logging on
sudo ufw --force enable
sudo ufw status verbose