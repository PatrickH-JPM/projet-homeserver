#!/bin/bash
# Fichier: install-docker.sh
# Emplacement: Project_homeserver/serveur/docker/install-docker.sh
# Langage: Bash
# Role: installe Docker Engine et Docker Compose sur la machine serveur, via le depot
#       officiel Docker (plus a jour que le paquet docker.io fourni par Ubuntu),
#       et autorise l'utilisateur courant a lancer docker sans sudo.
set -e
echo ">>> Suppression d'anciennes versions eventuelles"
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
echo ">>> Installation des prerequis"
sudo apt update
sudo apt install -y ca-certificates curl gnupg
echo ">>> Ajout de la cle GPG officielle Docker"
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo ">>> Ajout du depot officiel Docker"
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
echo ">>> Installation de Docker Engine, CLI, et du plugin Compose"
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
echo ">>> Autoriser l'utilisateur courant a utiliser docker sans sudo"
sudo usermod -aG docker $USER
echo ">>> Verification de l'installation"
sudo docker run hello-world
echo ">>> IMPORTANT : deconnecte-toi puis reconnecte-toi (ou redemarre la session SSH)"
echo