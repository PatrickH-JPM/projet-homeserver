#!/bin/bash
# Fichier: init-serveur.sh
# Emplacement: Project_homeserver/serveur/docker/init-serveur.sh
# Langage: Bash
# Role: prepare l'environnement avant l'installation des services (Pterodactyl, Portainer,
#       Uptime Kuma) - cree le reseau Docker partage et les dossiers de donnees persistantes.

#!/usr/bin/env bash
set -euo pipefail

sudo mkdir -p /var/lib/pterodactyl/volumes
sudo mkdir -p /var/log/pterodactyl
sudo mkdir -p /etc/pterodactyl

sudo chown -R patrick:docker /var/lib/pterodactyl /var/log/pterodactyl /etc/pterodactyl

echo "Arborescence Wings prete sur la machine serveur."
