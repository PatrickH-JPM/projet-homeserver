#!/bin/bash
# Fichier: setup-psad.sh
# Emplacement: Project_homeserver/serveur/firewall/setup-psad.sh
# Langage: Bash
# Role: installe psad et le configure pour analyser les logs deja produits par
#       ufw/nftables, afin de detecter les scans de port et calculer un niveau de danger.
set -e
echo ">>> Installation de psad"
sudo apt update
sudo apt install -y psad
echo ">>> Configuration : adresse email locale desactivee (alertes gerees par le NAS, pas ici)"
sudo sed -i 's/^EMAIL_ADDRESSES.*/EMAIL_ADDRESSES             root@localhost;/' /etc/psad/psad.conf
echo ">>> Configuration : activer l'interface de log utilisee (iptables via ufw)"
sudo sed -i 's/^ENABLE_SYSLOG_FILE.*/ENABLE_SYSLOG_FILE          Y;/' /etc/psad/psad.conf
echo ">>> Indiquer a psad le fichier de log a analyser"
sudo sed -i 's|^IPT_SYSLOG_FILE.*|IPT_SYSLOG_FILE             /var/log/ufw.log;|' /etc/psad/psad.conf
echo ">>> Mise a jour des signatures de scan connues"
sudo psad --sig-update
echo ">>> Redemarrage de psad"
sudo systemctl restart psad
echo ">>> Verification du statut"
sudo systemctl status psad --no-pager
sudo psad --