#!/bin/bash
# Fichier: setup-nftables.sh
# Emplacement: Project_homeserver/serveur/firewall/setup-nftables.sh
# Langage: Bash (commandes nft)
# Role: ajoute des regles de journalisation nftables qui distinguent explicitement,
#       dans le texte meme du log, une connexion de jeu reelle d'une simple tentative
#       de scan sur le port 49150 - sans avoir besoin de deduire quoi que ce soit.

set -e
echo ">>> Creation de la table et de la chaine dediees au marquage du port 49150"
sudo nft add table inet marquage 2>/dev/null || true
sudo nft add chain inet marquage input { type filter hook input priority -5 \; } 2>/dev/null || true
echo ">>> Regle 1 : paquet NEW (premiere tentative de connexion) = scan potentiel"
sudo nft add rule inet marquage input tcp dport 49150 ct state new log prefix "MC-SCAN-OU-NOUVELLE-CO: " level info
echo ">>> Regle 2 : paquet ESTABLISHED (connexion deja acceptee et active) = vrai joueur connecte"
sudo nft add rule inet marquage input tcp dport 49150 ct state established log prefix "MC-CONNEXION-JOUEUR-ACTIVE: " level info
echo ">>> Verification des regles en place"
sudo nft list table inet marquage