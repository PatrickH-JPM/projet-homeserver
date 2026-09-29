#!/bin/bash
# Fichier: install-wings.sh
# Emplacement: Project_homeserver/serveur/pterodactyl/wings/install-wings.sh
# Langage: Bash
# Role: installe le daemon Wings sur la machine serveur - c'est ce composant qui
#       execute reellement le conteneur Docker du serveur Minecraft, sur ordre du Panel.
set -e
echo ">>> Creation du dossier de configuration Wings"
sudo mkdir -p /etc/pterodactyl
echo ">>> Telechargement du binaire Wings (derniere version stable)"
sudo curl -L -o /usr/local/bin/wings \
  "https://github.com/pterodactyl/wings/releases/latest/download/wings_linux_amd64"
echo ">>> Rendre le binaire executable"
sudo chmod u+x /usr/local/bin/wings
echo ">>> Creation du service systemd pour lancer Wings automatiquement au demarrage"
sudo tee /etc/systemd/system/wings.service > /dev/null << 'EOF'
[Unit]
Description=Pterodactyl Wings Daemon
After=docker.service
Requires=docker.service
PartOf=docker.service
[Service]
User=root
WorkingDirectory=/etc/pterodactyl
LimitNOFILE=4096
PIDFile=/var/run/wings/daemon.pid
ExecStart=/usr/local/bin/wings
Restart=on-failure
StartLimitInterval=180
StartLimitBurst=30
RestartSec=5
[Install]
WantedBy=multi-user.target
EOF
echo ">>> Rechargement de systemd et activation du service (sans le demarrer, config.yml manquant)"
sudo systemctl daemon-reload
sudo systemctl enable wings
echo ">>> IMPORTANT : Wings n'est pas encore demarre."
echo ">>> Il faut d'abord creer le noeud dans le Panel (interface web) pour obtenir"
echo ">>> le fichier config.yml a placer dans /etc/pterodactyl/ avant de faire :"
echo ">>>