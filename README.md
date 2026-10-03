# Home_server V8
Guide principal : Architecture_reseau_securisee_-_Serveur_Minecraft_V8.docx.

Ordre : box, ER605, Ubuntu et SSH, pare-feu, Pterodactyl et Minecraft, recette publique, surveillance.

- Home_server : VLAN3, 192.168.3.10, Ubuntu Server 26.04.1 ou 24.04.
- Home_server_mc : VLAN4, 192.168.4.10, Ubuntu24.04, 9Go.
- Home_server_services : VLAN5, 192.168.5.10, Ubuntu24.04, 4Go.
- PC administrateur : VLAN2, IP reservee par defaut 192.168.2.50.
- WAN du jeu : mc-pathnas.myDS.me:49150 TCP, Java Edition.

Les commandes se lancent dans le terminal de la machine indiquee dans le guide.
Les scripts modifient les reseaux et les pare-feu : executer reseau-host.sh au clavier de Home_server.
Les fichiers copies par preparer.py sont repertories dans docs/guide.md decrit chaque etape. docs/chemins.csv.
Ne publier aucun fichier extrait de /etc/Home_server-deploiement, /etc/Home_server-mail ou /etc/Home_server-pki.
Les scripts ne publient pas de depot GitHub et ne configurent pas automatiquement la box ou l'ER605.

La syntaxe et les rendus sont controles localement. KVM, Docker, ER605, SMTP et le routage sont a valider sur le materiel.
