# Architecture réseau sécurisée du serveur Minecraft V8
Home_server — guide de mise en service — 3 octobre 2026

Home_server héberge deux machines virtuelles : Minecraft et ses outils d’administration. Les joueurs utilisent mc-pathnas.myDS.me:49150 sans VPN. Tu administres l’ensemble depuis ton PC gamer, par SSH et Visual Studio Code. L’ER605 bloque les accès du serveur vers le VLAN 2 et le réseau familial. Les journaux et Grafana s’installent après la mise en service du jeu.

--- INFO ---
La priorité est d’empêcher un serveur compromis d’atteindre les données privées. Aucun montage avec ce matériel ne garantit un risque nul. La protection dépend des ACL de l’ER605, de leur résistance à l’usurpation d’adresse et des tests réalisés. Les journaux conservés sur Home_server peuvent être falsifiés si cette machine est compromise.

## 1 Lire et exécuter le guide
--- INFO ---
INFO explique l’idée. FAIRE indique une action. CONTRÔLE indique le résultat attendu. Chaque ligne § est une commande ; copie son texte sans le symbole. Les blocs DÉBUT FICHIER et FIN FICHIER sont du contenu à enregistrer, sans leurs marqueurs.

Les commandes Linux s’exécutent dans le terminal de la machine indiquée. Les commandes PowerShell s’exécutent sur ton PC Windows. sudo donne temporairement les droits administrateur. Les scripts règlent les propriétaires et les droits des fichiers : aucune valeur numérique à mémoriser.

--- FAIRE ---
Suivre les chapitres 2 à 9 pour rendre Minecraft accessible. Poursuivre ensuite avec les chapitres 10 à 13 pour les VPN et la surveillance. Les tests de protection du chapitre 8 précèdent obligatoirement l’ouverture publique.

| Ordre | Résultat |
| 1 | Box préparée, redirections du jeu désactivées |
| 2 | ER605 configuré et réseaux privés protégés |
| 3 | Ubuntu installé sur Home_server et accès SSH depuis le PC |
| 4 | Pare-feu et deux VM préparés par les scripts |
| 5 | Pterodactyl et Minecraft fonctionnels |
| 6 | Isolation testée puis jeu ouvert publiquement |
| 7 | VPN personnel et ami validés |
| 8 | Journaux bruts, courriels et Grafana installés |

## 2 Matériel et plan réseau
--- INFO ---
Matériel existant : ER605, Home_server avec Core i5-4670, 16 Go DDR3 à 1600 MHz et SSD. Les deux VM partagent le processeur ; leurs vCPU ne sont pas des cœurs supplémentaires. Répartition initiale : 9 Go pour la VM jeu, 4 Go pour la VM services, environ 3 Go disponibles pour l’hôte.

Le VLAN est créé sur l’ER605. Ubuntu associe ensuite chaque numéro au bon réseau de VM. Un câble transporte le VLAN 3 sans marque et les VLAN 4 et 5 avec une marque. Le manuel ER605 V2 documente ces fonctions TAG, UNTAG et PVID [S1, S2].

| Réseau | Usage | Adresse du routeur | Machine |
| VLAN 2 | Réseau personnel existant | 192.168.2.1 | NAS et PC gamer |
| VLAN 3 | Home_server physique | 192.168.3.1 | Home_server 192.168.3.10 |
| VLAN 4 | Jeu | 192.168.4.1 | Home_server_mc 192.168.4.10 |
| VLAN 5 | Services | 192.168.5.1 | Home_server_services 192.168.5.10 |
| VPN | Clients WireGuard | 10.10.10.1 | PC .2, ami .3, téléphone .4 |

Ces adresses sont le plan de la V8, pas des valeurs constatées sur ton installation. Si ton VLAN 2 utilise déjà un autre sous-réseau, conserver sa configuration et adapter le dépôt avant exécution. Le réseau de la box doit être distinct de ces réseaux.

--- FAIRE ---
Dans la box, relever son adresse LAN et son masque. Exemple : adresse 192.168.1.1, masque 255.255.255.0 donnent le réseau familial 192.168.1.0/24. Noter aussi l’adresse WAN privée de l’ER605, sa version matérielle et son firmware. Réserver 192.168.2.50 au PC gamer dans l’ER605 ; le script accepte une autre IP du VLAN 2.

Home_server est le nom utilisé pour le matériel, les VM et les fichiers. Le nom technique Linux est home-server : les noms DNS utilisent des tirets. Le script fixe aussi le nom d’affichage Home_server.

## 3 Configurer la box
--- FAIRE ---
Ouvrir l’interface web de ta box depuis le PC gamer. Réserver l’IP WAN de l’ER605 dans le LAN de la box. Créer les deux redirections suivantes ; laisser celle du jeu désactivée jusqu’au chapitre 9.

| Port de la box | Destination | État initial |
| TCP 49150 | IP WAN de l’ER605, TCP 49150 | Désactivé |
| UDP 51820 | IP WAN de l’ER605, UDP 51820 | Actif après configuration WireGuard |

Limiter les redirections à ces deux entrées ; désactiver UPnP et l’administration de la box depuis Internet. Ne pas placer l’ER605 en DMZ. Ne créer aucune redirection vers une adresse du VLAN 2.

--- CONTRÔLE ---
L’adresse IPv4 publique affichée par la box doit être utilisable pour une redirection entrante. En cas de CGNAT ou de partage de ports par l’opérateur, l’ouverture peut nécessiter une modification gratuite proposée par l’opérateur ; la présence d’un DDNS ne résout pas ce point.

--- INFO ---
mc-pathnas.myDS.me désigne une adresse IP publique, pas intrinsèquement le NAS [S11]. Conserver ce nom ; aucun changement n’est nécessaire pour Minecraft. Dans DSM, vérifier que son entrée DDNS correspond à l’IPv4 publique de la box et que la mise à jour automatique fonctionne. Aucune redirection d’administration n’est nécessaire pour cette mise à jour. Les composants du serveur de jeu restent indépendants de DSM ; seul le nom existant est actualisé par son service DDNS.

## 4 Configurer l’ER605 depuis le PC gamer
--- INFO ---
Logiciel exact retenu : Microsoft Edge, sur Windows, pour l’interface web locale de l’ER605. Aucun contrôleur Omada supplémentaire n’est nécessaire en mode autonome. Cette procédure conserve ce mode ; elle ne prévoit pas d’adoption du routeur par un contrôleur [S2].

--- FAIRE ---
Ouvrir https://192.168.2.1 dans Edge si cette adresse est déjà celle du routeur. Sinon utiliser son adresse LAN actuelle. Vérifier que la page appartient bien à l’ER605 avant connexion. Définir un mot de passe administrateur distinct des comptes du serveur. Installer uniquement un firmware correspondant à la version matérielle inscrite sur l’appareil.

Dans Network > LAN, créer les réseaux VLAN 3, 4 et 5 avec les adresses du tableau précédent. Activer leur DHCP, plage 100 à 199. Les adresses .10 sont réservées aux machines, hors plage DHCP.

Dans Network > VLAN, régler les ports en identifiant leurs étiquettes physiques :

| Port LAN physique | VLAN non marqué et PVID | VLAN marqués | VLAN exclus |
| Port relié au PC gamer | 2 | Aucun | 3, 4, 5 |
| Port relié au NAS | 2 | Aucun | 3, 4, 5 |
| Port relié à Home_server | 3 | 4 et 5 | 1 et 2 |

Si un commutateur non administrable dessert déjà le PC et le NAS, il reste derrière un port VLAN 2. Home_server est connecté directement à son port ER605. Retirer explicitement les appartenances automatiques indésirables : un nouveau VLAN peut être ajouté aux autres ports par défaut [S2].

--- FAIRE ---
Dans Firewall > Access Control, créer les groupes d’adresses nécessaires puis les règles LAN → LAN ci-dessous, dans cet ordre. Toute autorisation porte sur une nouvelle connexion ; les réponses aux connexions autorisées doivent passer grâce au suivi d’état.

| Ordre | Source | Destination | Autorisation |
| 1 | PC gamer, IP réservée | Home_server .3.10 et VM .4.10/.5.10 | TCP 22 |
| 2 | PC gamer | .5.10 | TCP 443 |
| 3 | PC gamer | .4.10 | TCP 49150 et 2022 |
| 4 | VPN personnel .2 et .4 | VLAN 2, 3, 4 et 5 | Accès personnel |
| 5 | VPN ami .3 | .5.10 | TCP 443 uniquement |
| 6 | VPN ami .3 | .4.10 | TCP 2022 uniquement |
| 7 | .4.10 | .5.10 | TCP 443 et 1514 |
| 8 | .3.10 | .5.10 | TCP 1514 |
| 9 | .5.10 | .4.10 | TCP 8080, 9100 et 9940 |
| 10 | .5.10 | .3.10 | TCP 9100 |
| 11 | VLAN 3, 4 et 5 | VLAN 2 | Refus total |
| 12 | VPN ami .3 | Tous les autres réseaux | Refus total |
| 13 | VLAN 3, 4 et 5 | Autres VLAN et accès de gestion ER605 | Refus hors exceptions ci-dessus |

L’administration du routeur lui-même peut relever d’un réglage de gestion distinct des ACL inter-VLAN. Limiter cette gestion au PC gamer et au VPN personnel. Tester le refus depuis Home_server et ses VM. Les refus ne doivent pas bloquer DNS/NTP publics ni les réponses aux flux autorisés.

--- FAIRE ---
Créer aussi les règles LAN → WAN suivantes. Le réseau familial se trouve côté WAN de l’ER605 ; une règle LAN → LAN ne le protège pas.

| Source | Destination | Règle |
| Tous les réseaux derrière l’ER605 | Sous-réseau LAN de la box, toutes ses IP | Refuser tous les protocoles |
| VLAN 3, 4 et 5 | Autres plages privées, locales et partagées | Refuser hors flux internes explicitement permis |
| VLAN 3, 4 et 5 | Internet public | DNS vers 9.9.9.9 et 149.112.112.112, TCP/UDP 53 ; NTP UDP123 ; TCP80/443 |
| VLAN 5 | IP du relais de courrier choisi plus tard | TCP587, après chapitre 12 |
| VPN personnel | Internet public | Autoriser, avec sortie WAN et NAT |

Plages privées/locales à couvrir : 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 100.64.0.0/10 et 169.254.0.0/16. Placer les refus avant les autorisations Internet. Ne pas bloquer la seule circulation de réponses déjà autorisées. Les requêtes sortantes destinées à des services publics passent par la passerelle sans exiger une connexion applicative à l’IP privée de la box.

--- FAIRE ---
Dans NAT > Virtual Servers, préparer TCP49150 vers 192.168.4.10:49150 ; laisser l’entrée désactivée. Le port UDP51820 arrive sur le service WireGuard de l’ER605 lui-même, sans redirection vers une VM. Désactiver UPnP, administration distante WAN et IPv6 sur les réseaux 3 à 5 pour cette version IPv4 du projet.

--- CONTRÔLE ---
Les capacités TAG/UNTAG sont documentées. En revanche, l’efficacité des ACL VPN, le suivi d’état, les restrictions de gestion et l’usurpation de source doivent être vérifiés sur ton firmware : aucun résultat n’est présumé acquis. Si une règle de refus est contournable, ne pas ouvrir le jeu ; la recette identifie précisément le point à corriger avec le matériel présent.

## 5 Installer Ubuntu sur Home_server
--- INFO ---
L’ISO ubuntu-26.04.1-live-server-amd64.iso d’environ 2,7 Go est bien l’image Ubuntu Server officielle pour ce processeur [S3]. Une ISO est l’image d’un support d’installation. Elle doit être écrite sur une clé USB amorçable, et non simplement copiée comme un fichier.

--- FAIRE SUR LE PC GAMER ---
Télécharger Rufus depuis https://rufus.ie et Ubuntu Server depuis https://releases.ubuntu.com/26.04/. Comparer l’empreinte de l’ISO au fichier SHA256SUMS de cette page. Dans PowerShell Windows, la commande suivante calcule l’empreinte du fichier téléchargé ; adapter son chemin si nécessaire.

§ Get-FileHash "$env:USERPROFILE\Downloads\ubuntu-26.04.1-live-server-amd64.iso" -Algorithm SHA256

Dans Rufus : sélectionner la clé USB, sélectionner l’ISO, choisir GPT si le BIOS démarre en UEFI, puis Démarrer. L’écriture efface la clé sélectionnée. Brancher ensuite la clé sur Home_server. Ouvrir son menu de démarrage au lancement du PC et choisir la clé en mode UEFI. Le nom de la touche dépend de la carte mère et s’affiche généralement au démarrage.

--- FAIRE SUR HOME_SERVER ---
Installer Ubuntu Server sur le SSD destiné au projet. Ce choix efface les données du disque sélectionné. Utiliser le réseau DHCP du VLAN 3 pour l’installation. Créer l’utilisateur patrick, choisir home-server comme nom technique, puis cocher Install OpenSSH server. Ne sélectionner aucun service supplémentaire. Retirer la clé USB lorsque l’installation demande le redémarrage.

Au clavier de Home_server, se connecter sous patrick. Dans son terminal Linux :

§ hostname -I

--- CONTRÔLE ---
Noter l’IP obtenue, normalement 192.168.3.100 à 199. Elle sert seulement au premier accès ; le script fixera ensuite 192.168.3.10.

## 6 Accéder au terminal et aux fichiers depuis Windows
--- FAIRE SUR LE PC GAMER ---
Installer Visual Studio Code depuis https://code.visualstudio.com et son extension Microsoft Remote - SSH, identifiant ms-vscode-remote.remote-ssh [S4]. Installer Git for Windows depuis https://git-scm.com/download/win pour publier le dépôt. Aucun abonnement Copilot n’est nécessaire.

Dans PowerShell Windows, vérifier le client SSH et créer une clé. S’il existe déjà une clé adaptée, conserver celle-ci ; ne pas l’écraser.

§ ssh -V
§ ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\Home_server" -C "Home_server administration"

Choisir une phrase secrète. La clé privée reste sur le PC ; seul le fichier .pub est transmis. Remplacer IP_INITIALE par l’adresse notée au chapitre 5. Au premier accès, comparer l’empreinte affichée avec celle relevée localement sur Home_server par sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub.

§ Get-Content "$env:USERPROFILE\.ssh\Home_server.pub" | ssh patrick@IP_INITIALE 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys'
§ ssh -i "$env:USERPROFILE\.ssh\Home_server" patrick@IP_INITIALE

--- INFO ---
Tu disposes maintenant du terminal Linux dans une fenêtre du PC : les commandes suivantes s’exécutent sur Home_server. Après configuration, VS Code offrira le même terminal et modifiera directement les fichiers distants. Les sessions SSH ne donnent pas au serveur une autorisation de connexion vers le PC ; garder le transfert d’agent désactivé.

--- FAIRE SUR LE PC GAMER ---
Extraire l’archive V8 dans un dossier local. Dans VS Code, ouvrir Home_server_v8, puis Source Control > Initialize Repository > Publish to GitHub. Publier uniquement le contenu fourni. Choisir un dépôt public sans secrets pour simplifier le téléchargement initial. Noter son URL HTTPS ; aucun dépôt n’a été publié automatiquement.

Dans le terminal Linux de Home_server, remplacer TON_COMPTE et TON_DEPOT par cette URL réelle.

§ sudo apt update
§ sudo apt install -y git python3
§ git clone https://github.com/TON_COMPTE/TON_DEPOT.git ~/Home_server_v8
§ cd ~/Home_server_v8
§ sudo python3 scripts/assistant.py host
§ sudo bash /usr/local/lib/Home_server-v8/installer-base.sh host

--- INFO ---
L’assistant affiche les cartes réseau et propose le nom de la carte unique. Il demande aussi le sous-réseau familial et l’IP réservée du PC. La configuration de la carte, appelée Netplan, est écrite automatiquement. Aucun fichier réseau n’est à rédiger à la main.

--- FAIRE AU CLAVIER DE HOME_SERVER ---
Lancer le changement réseau sur le clavier et l’écran directement branchés à Home_server. Saisir CONSOLE lorsque le script le demande.

§ sudo bash /usr/local/lib/Home_server-v8/reseau-host.sh

--- FAIRE SUR LE PC GAMER ---
Ouvrir dans VS Code le fichier C:\Users\TON_UTILISATEUR\.ssh\config. Remplacer le chemin de clé par ton chemin Windows réel.

DÉBUT FICHIER
Host Home_server
    HostName 192.168.3.10
    User patrick
    IdentityFile C:/Users/TON_UTILISATEUR/.ssh/Home_server
    ForwardAgent no
Host Home_server_mc
    HostName 192.168.4.10
    User patrick
    IdentityFile C:/Users/TON_UTILISATEUR/.ssh/Home_server
    ForwardAgent no
Host Home_server_services
    HostName 192.168.5.10
    User patrick
    IdentityFile C:/Users/TON_UTILISATEUR/.ssh/Home_server
    ForwardAgent no
FIN FICHIER

Dans VS Code : F1 > Remote-SSH: Connect to Host > Home_server. Ouvrir /home/patrick/Home_server_v8 puis Terminal > New Terminal. L’édition y est directe. Tu peux ouvrir / pour consulter l’arborescence entière ; les fichiers système restent protégés. Pour modifier une configuration protégée, utiliser sudo nano CHEMIN dans ce terminal. Dans nano : Ctrl+O, Entrée pour enregistrer ; Ctrl+X pour fermer.

## 7 Créer les VM et installer les pare-feu
--- INFO ---
Une VM est un ordinateur Linux séparé exécuté dans Home_server. Le script télécharge une image Ubuntu 24.04 officielle déjà installée, vérifie sa somme et prépare chaque VM avec ta clé publique [S5]. Il n’y a ni seconde clé USB ni installation Linux interactive à réaliser. Ubuntu24.04 est retenu pour les VM parce que Pterodactyl le documente comme système pris en charge [S6].

--- FAIRE DANS LE TERMINAL VS CODE HOME_SERVER ---

§ sudo python3 /usr/local/lib/Home_server-v8/vm.py /home/patrick/.ssh/authorized_keys
§ sudo virsh -c qemu:///system list --all

Le fichier authorized_keys doit contenir une seule clé ED25519 pour cette création ; le script refuse un fichier comportant plusieurs lignes. Les disques sont créés sur le SSD, 60 Go virtuels par VM ; le script refuse de remplacer un disque ou une VM existants.

--- CONTRÔLE ---
Attendre la fin du premier démarrage. Dans VS Code, ouvrir une connexion Home_server_mc puis Home_server_services. Dans chaque terminal de VM :

§ cloud-init status --wait

Le résultat attendu est done. Si SSH n’est pas encore disponible, laisser le premier démarrage terminer et consulter la VM depuis Home_server avec sudo virsh console NOM_VM. Ctrl+] quitte cette console. Les VM utilisent la clé SSH du PC ; aucun mot de passe de connexion n’a été créé.

--- FAIRE DANS HOME_SERVER_MC ---

§ git clone https://github.com/TON_COMPTE/TON_DEPOT.git ~/Home_server_v8
§ cd ~/Home_server_v8
§ sudo python3 scripts/assistant.py game
§ sudo bash /usr/local/lib/Home_server-v8/installer-base.sh game
§ sudo bash /usr/local/lib/Home_server-v8/docker.sh

--- FAIRE DANS HOME_SERVER_SERVICES ---

§ git clone https://github.com/TON_COMPTE/TON_DEPOT.git ~/Home_server_v8
§ cd ~/Home_server_v8
§ sudo python3 scripts/assistant.py services
§ sudo bash /usr/local/lib/Home_server-v8/installer-base.sh services
§ sudo bash /usr/local/lib/Home_server-v8/docker.sh

--- INFO ---
Le pare-feu de l’hôte protège son administration. Dans les VM, iptables filtre les services et la chaîne DOCKER-USER filtre les ports Docker [S7]. Les refus vers les réseaux privés restent doublés sur l’ER605 : un attaquant administrateur de Home_server peut modifier tous ses filtres Linux.

Les cartes des VM sont attachées uniquement à leur réseau, avec le filtre libvirt clean-traffic et leur IP fixe [S8]. Aucune VM ne reçoit le réseau VLAN 2. Les scripts imposent aussi le démarrage du pare-feu avant les services qu’ils protègent.

--- CONTRÔLE DANS CHAQUE MACHINE ---

§ bash /usr/local/lib/Home_server-v8/controle.sh

Vérifier les IP .3.10, .4.10 et .5.10 sur les machines correspondantes. La commande de contrôle affiche les règles présentes ; elle ne remplace pas les essais de routage du chapitre 8.

## 8 Tester la protection avant le jeu public
--- FAIRE ---
Utiliser le PC gamer comme cible de test à la place des données privées. Sur le PC, installer Wireshark depuis https://www.wireshark.org. Dans PowerShell administrateur, créer temporairement un port de test ; Python3 doit être installé depuis python.org ou Microsoft Store.

§ New-NetFirewallRule -DisplayName "Home_server test isolation" -Direction Inbound -Protocol TCP -LocalPort 8765 -Action Allow
§ python -m http.server 8765 --bind 0.0.0.0

Depuis un autre poste du VLAN 2, vérifier d’abord que http://192.168.2.50:8765 répond. Cette vérification évite de confondre une ACL efficace avec un serveur de test arrêté. Dans chacune des VM et Home_server :

§ curl --connect-timeout 3 http://192.168.2.50:8765

--- CONTRÔLE ---
Les trois tentatives doivent échouer. Tester également l’interface de la box avec son IP réelle :

§ curl --connect-timeout 3 http://IP_BOX

Les trois tentatives doivent échouer. Vérifier aussi les ports réels de gestion du NAS avec un simple test de connexion, sans authentification ni écriture ; aucun accès ne doit réussir depuis les trois machines.

--- FAIRE DEPUIS HOME_SERVER ---
Vérifier l’ER605 indépendamment du pare-feu Linux. Installer Scapy, puis lancer le script fourni : il envoie quelques paquets de test sans modifier les adresses ni désactiver le pare-feu.

§ sudo apt install -y python3-scapy
§ sudo python3 /usr/local/lib/Home_server-v8/test-isolation.py

Dans Wireshark sur le PC gamer, capturer l’interface physique du VLAN 2 avec le filtre tcp.port == 8765. Aucun SYN issu de ces essais ne doit atteindre le PC. Le script teste les VLAN 3/4/5, une adresse source VPN usurpée et une marque VLAN2 interdite. Il contourne les filtres IP locaux par une émission Ethernet, pour éprouver le routeur.

--- CONTRÔLE ---
Un paquet reçu sur le PC signifie que l’isolation demandée n’est pas validée, même si aucune connexion ne s’établit. Corriger la règle ou l’appartenance VLAN concernée avant de poursuivre. Le test est un contrôle ciblé, pas une preuve universelle d’absence de faille.

--- FAIRE SUR LE PC ---
Fermer le serveur de test avec Ctrl+C, puis retirer son exception Windows.

§ Remove-NetFirewallRule -DisplayName "Home_server test isolation"

## 9 Installer Pterodactyl et ouvrir Minecraft
--- INFO ---
Le Panel est la page web d’administration. Wings exécute ses demandes sur la VM jeu. Les connexions d’administration sont chiffrées en HTTPS. Le certificat local permet à ton navigateur et à Wings de reconnaître ces services privés. Les joueurs Minecraft n’ont aucun certificat à installer.

--- FAIRE DANS HOME_SERVER_SERVICES ---

§ sudo python3 /usr/local/lib/Home_server-v8/telecharger-app.py
§ sudo bash /usr/local/lib/Home_server-v8/installer-applications.sh services
§ sudo bash /usr/local/lib/Home_server-v8/pki.sh
§ sudo bash /usr/local/lib/Home_server-v8/panel.sh

Le téléchargement choisit la release stable officielle disponible et enregistre sa version et son empreinte. Le dernier script crée la base et demande les informations du compte administrateur : utiliser ton adresse, ton nom et un mot de passe unique. Choisir administrateur pour Patrick.

--- FAIRE SUR LE PC GAMER ---
Dans PowerShell, récupérer les certificats et le paquet de la VM jeu. Les commandes utilisent ta clé et ne passent pas par WSL.

§ New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh\Home_server-pki"
§ scp -i "$env:USERPROFILE\.ssh\Home_server" patrick@192.168.5.10:/home/patrick/Home_server-ca.crt "$env:USERPROFILE\.ssh\Home_server-pki\ca.crt"
§ scp -i "$env:USERPROFILE\.ssh\Home_server" patrick@192.168.5.10:/home/patrick/Home_server-ca-private.tar "$env:USERPROFILE\.ssh\Home_server-pki\ca-private.tar"
§ scp -i "$env:USERPROFILE\.ssh\Home_server" patrick@192.168.5.10:/home/patrick/Home_server-wings-tls.tar "$env:USERPROFILE\.ssh\Home_server-pki\wings-tls.tar"
§ Import-Certificate -FilePath "$env:USERPROFILE\.ssh\Home_server-pki\ca.crt" -CertStoreLocation Cert:\CurrentUser\Root
§ scp -i "$env:USERPROFILE\.ssh\Home_server" "$env:USERPROFILE\.ssh\Home_server-pki\wings-tls.tar" patrick@192.168.4.10:/home/patrick/

Conserver ca-private.tar dans ce dossier privé du PC, hors Git et hors synchronisation. Cette clé permet de renouveler les certificats ; elle ne doit pas rester sur les VM. La génération initiale s’effectue sur une VM fraîche, avant son ouverture.

Dans Home_server_services, après vérification des copies sur le PC :

§ sudo rm /root/Home_server-pki/ca.key /home/patrick/Home_server-ca-private.tar /home/patrick/Home_server-wings-tls.tar

Sur le PC, ouvrir le Bloc-notes en administrateur, puis C:\Windows\System32\drivers\etc\hosts. Ajouter ce contenu :

DÉBUT FICHIER
192.168.5.10 panel.home.arpa grafana.home.arpa wings.home.arpa
192.168.4.10 wings-game.home.arpa
FIN FICHIER

Dans Home_server_mc :

§ sudo python3 /usr/local/lib/Home_server-v8/telecharger-app.py
§ sudo bash /usr/local/lib/Home_server-v8/installer-applications.sh game
§ sudo bash /usr/local/lib/Home_server-v8/tls-game.sh /home/patrick/Home_server-wings-tls.tar
§ rm /home/patrick/Home_server-wings-tls.tar

Dans Home_server_services :

§ sudo bash /usr/local/lib/Home_server-v8/activer-jeu.sh

--- FAIRE DANS EDGE SUR LE PC GAMER ---
Ouvrir https://panel.home.arpa et se connecter. Le navigateur doit reconnaître le certificat après import de la CA. Dans l’administration Pterodactyl : créer une Location Tours, puis un Node Home_server_mc avec les paramètres suivants.

| Paramètre du Node | Valeur |
| FQDN | wings.home.arpa |
| Communication | HTTPS, derrière un proxy |
| Port du daemon vu par le Panel | 443 |
| Port SFTP | 2022 |
| Mémoire disponible annoncée | 8192 MiB |
| Disque annoncé | 45000 MiB |
| Répertoire des données | /var/lib/pterodactyl/volumes |

Dans Node > Configuration, copier la configuration complète. Dans le terminal Home_server_mc, ouvrir le fichier suivant avec nano puis y coller ce contenu.

§ sudo nano /etc/pterodactyl/config.yml
§ sudo python3 /usr/local/lib/Home_server-v8/wings.py
§ sudo bash /usr/local/lib/Home_server-v8/activer-jeu.sh

Le script conserve les identifiants et les jetons générés ; il ajoute le chiffrement et les restrictions réseau. Le proxy autorisé de Wings est uniquement 192.168.5.10. Le Panel ne reçoit pas de proxy public et ne fait pas confiance à toutes les sources.

--- CONTRÔLE ---
Le Node doit apparaître connecté dans le Panel. Si ce n’est pas le cas, consulter depuis Home_server_mc :

§ sudo journalctl -u wings -n 50 --no-pager

--- FAIRE DANS LE PANEL ---
Créer l’allocation 192.168.4.10:49150. Créer le serveur Home_server_minecraft avec l’egg Paper fourni, choisir une version de Minecraft compatible avec son image Java, affecter 7168 MiB de RAM et cette allocation. Accepter l’EULA Minecraft au démarrage. Le mode de jeu et les règles d’admission des joueurs restent tes paramètres applicatifs ; ils ne constituent pas la séparation réseau.

Vérifier dans la console Pterodactyl le message Done (...). Depuis Minecraft sur ton PC gamer, utiliser 192.168.4.10:49150. Vérifier connexion, déconnexion, arrêt et redémarrage depuis le Panel. Le PC gamer sert ici de poste de recette.

--- FAIRE APRÈS RÉUSSITE DU CHAPITRE 8 ---
Activer TCP49150 sur l’ER605 et sur la box. Depuis un autre accès Internet, sans WireGuard, rejoindre mc-pathnas.myDS.me:49150. Le port personnalisé fait partie de l’adresse à saisir ; aucun plugin ni VPN joueur n’est requis.

--- CONTRÔLE ---
Depuis l’extérieur, SSH22, SFTP2022, Wings8080, Panel443 et les ports de supervision doivent être inaccessibles. Seul TCP49150 est redirigé vers le serveur. Cette version concerne Minecraft Java ; aucune ouverture UDP du jeu n’est prévue.

## 10 Configurer les accès WireGuard
--- INFO ---
WireGuard reste hébergé sur l’ER605. Le profil personnel transporte Internet et permet l’accès à tous les VLAN du projet. Le profil ami transporte uniquement les adresses du Panel et de la VM jeu. Les droits sont imposés sur le routeur et les services, pas uniquement par la configuration du client [S12].

Chaque appareil possède sa propre paire de clés. Le PC personnel utilise .2, le téléphone .4 et l’ami .3. Deux appareils ne partagent pas une clé et une IP. Le téléphone peut donc rester connecté en même temps que le PC.

--- FAIRE ---
Installer WireGuard for Windows depuis https://www.wireguard.com/install/ et l’application officielle WireGuard sur Android. Créer un tunnel vide sur chaque appareil : l’application génère les clés. Copier seulement la clé publique vers l’ER605.

Dans VPN > WireGuard, créer l’interface avec 10.10.10.1/24 et UDP51820. Sur l’ER605, créer un Peer par appareil, avec sa clé publique et Allowed Address limité à son IP VPN /32. Ces /32 authentifient les adresses des pairs ; ne pas y saisir 0.0.0.0/0.

Dans les applications clientes, compléter les champs suivants. Chaque fichier conserve la clé privée générée sur son appareil.

| Champ client | Patrick PC | Patrick téléphone | Ami |
| Address | 10.10.10.2/32 | 10.10.10.4/32 | 10.10.10.3/32 |
| Endpoint | mc-pathnas.myDS.me:51820 | Même valeur | Même valeur |
| PublicKey du Peer | Clé publique ER605 | Même valeur | Même valeur |
| AllowedIPs | 0.0.0.0/0, ::/0 | 0.0.0.0/0, ::/0 | 192.168.5.10/32, 192.168.4.10/32 |
| DNS | 9.9.9.9 | 9.9.9.9 | DNS du client conservé |
| PersistentKeepalive | 25 | 25 | 25 |

Le tunnel transporte IPv4. ::/0 capture aussi IPv6 côté client pour éviter une sortie Internet IPv6 hors tunnel ; l’ER605 ne fournit pas de sortie IPv6 dans ce projet. Tester sur chaque application : si IPv6 sort toujours hors tunnel, corriger la configuration cliente avant d’utiliser ce profil comme sortie Internet de Tours.

--- FAIRE POUR L’AMI ---
Créer un compte Pterodactyl non administrateur et l’ajouter comme sous-utilisateur du seul serveur Minecraft. Autoriser console, commandes, démarrage, arrêt, redémarrage, fichiers et SFTP selon les tâches confiées. Ne lui donner ni compte Linux, ni clé SSH, ni droit de créer des Node ou des allocations. Ajouter panel.home.arpa et wings.home.arpa à son fichier hosts ; lui transmettre uniquement ca.crt pour l’import du certificat.

--- CONTRÔLE À DISTANCE ---
Patrick PC et téléphone : l’IPv4 publique observée doit être celle de Tours ; accès au VLAN2 et à l’administration autorisés. Ami : Panel et fonctions Minecraft disponibles, Grafana refusé, SSH refusé, VLAN2 refusé, routeur et réseau familial refusés. Tester aussi ces refus après modification volontaire des AllowedIPs du profil ami : le routeur doit toujours les imposer.

Une sortie Internet française ne garantit pas qu’un fournisseur de comptes ignorera ton déplacement ou ses contrôles d’authentification.

## 11 Installer le journal brut en direct
--- INFO ---
Rsyslog est le récepteur. Il conserve les messages reçus dans brut.log sans traduction ni réécriture du contenu. Il écrit en parallèle la source et la gravité dans evenements.jsonl. Les mails lisent directement ce second fichier. Alloy et Grafana constituent une branche distincte [S9].

ER605 → UDP514 sur Home_server_services. Home_server et Home_server_mc → TCP1514 sur Home_server_services. Aucun récepteur n’est installé dans le VLAN2. Les transports syslog ne prouvent pas l’authenticité des messages : les sources sont limitées par les ACL et les pare-feu, mais une source compromise peut mentir.

--- FAIRE SUR CHAQUE MACHINE LINUX ---
Lancer maintenant les composants de surveillance.

§ sudo bash /usr/local/lib/Home_server-v8/monitoring.sh

Sur l’ER605 : System Tools > System Log, activer Send Log vers 192.168.5.10. Le port autonome utilisé est UDP514. Choisir le niveau le plus détaillé proposé ; vérifier ensuite les messages effectivement reçus. Noter la source observée si elle diffère de 192.168.5.1 et ajuster router_syslog_ip dans /etc/Home_server-deploiement/parametres.json et les filtres correspondants.

Sur Home_server_mc, relever l’UUID complet du serveur dans le Panel, puis remplacer UUID_REEL.

§ sudo bash /usr/local/lib/Home_server-v8/journaux-minecraft.sh UUID_REEL

--- FAIRE DANS HOME_SERVER_SERVICES ---
Ouvrir un onglet de terminal VS Code consacré au suivi en direct. Ctrl+C ferme l’affichage sans arrêter la collecte.

§ sudo tail -F /var/log/Home_server/brut.log

--- CONTRÔLE ---
Depuis Minecraft : connexion et déconnexion doivent apparaître avec le nom du joueur. Après redémarrage, le message Done doit apparaître. Depuis Home_server :

§ logger -p user.err -t Home_server-test "SECURITY test de reception"

Ce message doit apparaître dans brut.log et evenements.jsonl sur Home_server_services. Tester également un événement ER605 identifiable, par exemple une connexion administrateur ; vérifier sa réception sans présumer que toutes les ACL produisent un journal.

## 12 Activer les courriels gratuits
--- INFO ---
SMTP est le protocole d’envoi de courriels, pas nécessairement un service payant. Le montage utilise une boîte de messagerie autorisant l’envoi automatisé. Exemple gratuit : Gmail personnel avec validation en deux étapes et mot de passe d’application, lorsque Google rend cette fonction disponible pour le compte [S10]. Le mot de passe principal n’est pas utilisé.

Sans compte compatible, relais opérateur disponible ou fournisseur acceptant cet usage, l’envoi fiable de mails vers Internet n’est pas assuré. Le Centre des journaux DSM dépend lui aussi d’un moyen d’envoi. Héberger directement un serveur de courrier sur une connexion domestique ne garantit ni délivrabilité ni gratuité opérationnelle.

--- FAIRE ---
Sur ton compte Gmail, activer la validation en deux étapes puis créer un mot de passe d’application dédié Home_server. Dans Home_server_services :

§ sudo python3 /usr/local/lib/Home_server-v8/mail.py

L’assistant demande l’adresse expéditrice, le destinataire et le mot de passe d’application, sans l’afficher. Il imprime les IP SMTP à autoriser en TCP587 dans la règle VLAN5 → WAN de l’ER605. Ajouter ces destinations exactes ; si le fournisseur les change, cette liste devra être actualisée.

§ sudo -u Home_servermail /usr/local/sbin/Home_server-mail.py --test
§ sudo systemctl enable --now Home_server-mail.timer

--- CONTRÔLE ---
Recevoir le courriel de test. Refaire connexion, déconnexion et démarrage Minecraft, puis le message SECURITY de test. Le regroupement est de dix secondes au minimum ; la réception finale dépend du fournisseur. Lorsqu’un envoi échoue, les événements sélectionnés restent en attente.

| Événement | Traitement prévu |
| Joueur connecté ou déconnecté | Courriel et journal avec nom ; adresse lors du logged in |
| Minecraft prêt | Courriel sur message Done |
| Erreur ou exception Minecraft | Courriel sur ERROR, Exception et gravité élevée |
| Arrêt ou fin de processus | Journal Docker, courriel ; vérifier le contexte avant de conclure à un crash |
| IP bannie ou décision CrowdSec | Journal et courriel de décision |
| Accès refusé ou vers un réseau privé | Journal et courriel regroupé |
| Scan suspecté | Alerte si 20 ports distincts observés pour une source en 60 secondes |
| Connexion administrateur SSH | Journal et courriel Accepted publickey |
| Compromission soupçonnée | Alerte sur tentative vers les réseaux protégés ou événement de sécurité |
| Compromission confirmée par analyse | Enregistrer explicitement SECURITY CONFIRMED avec les preuves identifiées |

La détection de scan ne couvre que les flux remontés par conntrack ; les paquets rejetés avant lui peuvent ne pas être comptés. Une connexion TCP autorisée n’est pas un joueur authentifié. Une IP inconnue n’est pas une preuve d’intrusion. Il n’existe pas de détection automatique universelle de « compromission avérée ».

--- FAIRE EN CAS DE COMPROMISSION CONFIRMÉE ---
Désactiver immédiatement la redirection du jeu sur la box et débrancher le câble de Home_server. Examiner ensuite les journaux propres de l’ER605 depuis le PC gamer. Les traces du serveur peuvent être altérées ; ne pas s’en servir seules pour innocenter le réseau privé.

## 13 Installer Grafana et les décisions de bannissement
--- INFO ---
Le script monitoring.sh télécharge les images officielles Loki, Prometheus, Grafana et Alloy, puis conserve leurs digests. Grafana consulte Prometheus pour les mesures et Loki pour les journaux. Il ne conditionne pas l’envoi des courriels [S9].

--- FAIRE SUR LE PC GAMER ---
Ouvrir https://grafana.home.arpa. Utilisateur initial admin. Lire le mot de passe initial dans Home_server_services avec sudo nano /opt/Home_server-monitoring/.env, puis le changer dans Grafana. Les tableaux fournis sont regroupés sous le dossier du projet.

| Tableau | Contenu |
| Systèmes | CPU, RAM, disponibilité, uptime, réseau, état et redémarrages des conteneurs, services, état SMTP |
| Minecraft | TPS, joueurs, durée des ticks, RAM Java, chunks, entités, disponibilité de l’exporteur |
| Réseau et événements | ER605, flux conntrack, refus, connexions Minecraft, erreurs, décisions CrowdSec |

Les mesures et l’actualisation des tableaux sont configurées à deux secondes. Cela ne garantit pas deux secondes de retard de bout en bout : la source, la file des logs et la charge CPU ajoutent leur propre délai. Le comptage des conteneurs ne lance jamais deux collectes concurrentes.

--- FAIRE POUR LES TPS ---
Sur le dépôt officiel https://github.com/sladkoff/minecraft-prometheus-exporter, télécharger le JAR compatible avec ta version de Paper. Le placer via Files du Panel dans plugins/, puis redémarrer une première fois. Dans le dossier de configuration créé par le plugin, ouvrir config.yml et reporter le contenu de exemples/plugin-config.yml du dépôt. Redémarrer.

Ajouter l’allocation 192.168.4.10:9940 au Node, puis l’affecter comme allocation supplémentaire à ce serveur. Ce port n’est jamais redirigé sur la box et n’est autorisé que depuis Home_server_services. Il exporte les métriques, pas l’administration du jeu.

Dans Home_server_services :

§ curl --max-time 3 http://192.168.4.10:9940/metrics

--- CONTRÔLE ---
Le résultat doit contenir mc_tps et mc_players_online_total. Leur absence signifie que la version/configuration du plugin ne fournit pas les données attendues ; un graphique vide ne doit pas être interprété comme une valeur nulle. L’exporteur fourni est prévu pour Paper/Bukkit, pas pour tous les serveurs moddés [S13].

--- FAIRE DANS LES DEUX VM ---
Installer ensuite CrowdSec et son bouncer iptables, configuré pour gérer seulement la liste IPset utilisée par le pare-feu [S14].

§ sudo bash /usr/local/lib/Home_server-v8/crowdsec.sh
§ sudo cscli metrics
§ sudo cscli decisions list

Le script installe les collections SSH et nginx lorsque le service existe. Ces collections ne constituent pas un analyseur de vulnérabilités Minecraft. Les décisions locales des deux VM restent distinctes ; le journal central permet de les identifier.

Sur Home_server_mc, tester un bannissement avec l’IP publique d’un accès de test distinct de ton accès administrateur. Remplacer IP_TEST ; ne pas utiliser une IP choisie au hasard.

§ sudo cscli decisions add --ip IP_TEST --duration 2m --reason Home_server-test
§ sudo ipset list cs-Home_server-v4

Le client de test doit être refusé sur Minecraft, puis réautorisé après expiration. Vérifier le journal et le courriel. Les décisions automatiques doivent être visibles séparément des simples refus de pare-feu.

--- INFO ---
Ce qui reste observable : les journaux réellement émis par l’ER605, les services Linux, Minecraft, Docker et les métadonnées de connexions conntrack. Cela ne donne ni le contenu chiffré, ni tous les échanges du VLAN2, ni un historique garanti de chaque paquet familial. Les messages de refus sont volontairement limités en fréquence ; un flot hostile ne produit pas un mail par paquet. Une machine compromise peut arrêter toute cette surveillance.

## 14 Recette finale
--- FAIRE ---
Cocher après observation réelle, depuis la source indiquée. Conserver les résultats dans un fichier local hors du dépôt public.

| Source et test | Résultat attendu |
| PC gamer → SSH des trois machines | Réussite |
| PC gamer → Panel et console WebSocket | Réussite |
| PC gamer → Minecraft privé | Réussite |
| Internet sans VPN → mc-pathnas.myDS.me:49150 | Réussite |
| Internet → SSH, Panel, Wings, Grafana, exporteurs | Refus |
| Chaque machine serveur → VLAN2 et NAS | Refus |
| Chaque machine serveur → LAN familial et interface box | Refus |
| Chaque machine serveur → gestion ER605 | Refus |
| VLAN2 marqué depuis port Home_server | Aucun paquet reçu sur PC |
| Source VPN usurpée depuis port Home_server | Aucun paquet reçu sur PC |
| Patrick PC et téléphone → VLAN2 | Réussite par WireGuard |
| Patrick → Internet depuis réseau extérieur | IPv4 publique de Tours, aucune sortie IPv6 hors tunnel |
| Ami → Panel et serveur assigné | Réussite |
| Ami → SSH, Grafana, NAS, routeur et autres serveurs | Refus |
| Ami avec AllowedIPs volontairement élargis | Mêmes refus |
| Redémarrage Home_server puis VM | Filtres et services présents ; aucune exposition nouvelle |
| Port Docker supplémentaire non prévu | Refus depuis source non autorisée |
| Connexion et déconnexion joueur | Journal brut, Grafana et mail |
| Minecraft prêt et erreur de test | Journal et mail |
| Arrêt contrôlé depuis Panel | État arrêté identifié, contexte conservé |
| Bannissement temporaire IP de test | Refus, décision visible, mail, expiration fonctionnelle |
| Syslog ER605 et logger de chaque machine | Source correcte dans le journal central |
| Rotation du journal | tail -F poursuit ; mails ne réenvoient pas tout l’historique |
| Arrêt de Grafana | Mails toujours fonctionnels |
| Erreur SMTP provoquée avec secret de test invalide | Événements en attente ; métrique erreur visible |
| Retour d’une configuration SMTP valide | Réception des événements retenus |
| Panel accessible par IP et par nom | Contrôles d’accès nginx conservés |

Pour le test du port Docker, lancer un conteneur de test sur un port non autorisé depuis la VM jeu, constater le refus depuis l’extérieur/VPN ami, puis le supprimer. Réaliser ce test sans ouvrir une nouvelle règle sur la box.

## 15 Fichiers et entretien
--- INFO ---
Le dépôt contient les scripts complets. docs/chemins.csv donne pour chaque fichier son rôle, son chemin final et ses droits. Les configurations réseau préparées sous /root/Home_server-a-valider ne sont pas appliquées automatiquement dans les VM : leur réseau a déjà été créé par le script VM.

| Emplacement | Usage |
| /home/patrick/Home_server_v8 | Copie Git éditable depuis VS Code |
| /usr/local/lib/Home_server-v8 | Scripts installés, protégés contre les comptes applicatifs |
| /etc/Home_server-deploiement/parametres.json | Paramètres de la machine |
| /etc/netplan/20-Home_server.yaml | Réseau de Home_server |
| /etc/Home_server-firewall.env | Paramètres du pare-feu de chaque VM |
| /etc/pterodactyl/config.yml | Configuration Wings et ses secrets |
| /var/www/pterodactyl/.env | Configuration privée du Panel |
| /etc/Home_server-pki | Certificats et clés des services |
| /var/log/Home_server/brut.log | Journal reçu sans réécriture du message |
| /var/log/Home_server/evenements.jsonl | Source, gravité, catégorie et message |
| /etc/Home_server-mail/config.json | Identifiants SMTP locaux |
| /opt/Home_server-monitoring | Configurations et tableaux Grafana |
| /var/lib/Home_server-monitoring | Historique des métriques et journaux |

--- FAIRE ---
Chaque mois : vérifier la réception d’un mail de test, l’arrivée des logs ER605, l’état des filtres et l’absence de redirection imprévue. Les scripts signalent aussi les certificats arrivant à expiration sous trente jours.

À six mois : installer les correctifs Ubuntu, ER605, Panel, Wings, plugins et supervision ; consulter les avis de sécurité ; retirer les comptes et clés inutilisés ; tester à nouveau les refus vers VLAN2 et réseau familial, le VPN ami et le bannissement. Renouveler les certificats avant leur échéance d’un an, avec la CA privée conservée sur le PC.

Pour actualiser le code du dépôt, dans le terminal Linux de chaque machine concernée :

§ cd ~/Home_server_v8
§ git status --short
§ git pull --ff-only

Le téléchargement ne réinstalle pas automatiquement les applications ni les certificats. Ne pas relancer les scripts d’initialisation Panel/VM sur une installation existante. Les correctifs de sécurité importants ne doivent pas attendre la revue semestrielle.

## 16 Cloudflare facultatif
--- INFO ---
Aucun composant du projet n’utilise Cloudflare. Spectrum pour Minecraft n’est pas disponible dans l’offre gratuite ; un Tunnel TCP demande un logiciel intermédiaire côté joueur. Ces deux options ne répondent pas simultanément à la gratuité et à l’accès par une simple adresse dans Minecraft [S15]. L’architecture retenue conserve l’accès direct avec le matériel existant.

## 17 Sources officielles et validation
Les documentations suivantes fondent les choix techniques ; consultation le 3 octobre 2026. Les contrôles réalisés ici portent sur les scripts, les fichiers et le rendu du document. Ils ne constituent pas une validation exécutée sur ton ER605 ou Home_server.

| Référence | Document officiel |
| S1 | TP-Link ER605 V2 User Guide, VLAN TAG/UNTAG et PVID — https://static.tp-link.com/upload/manual/2022/202208/20220830/1910013241_ER605%28UN%292.0_UG.pdf |
| S2 | TP-Link, plusieurs réseaux et ACL en mode autonome — https://www.tp-link.com/us/support/faq/3061/ |
| S3 | Canonical, images Ubuntu26.04.1 — https://releases.ubuntu.com/26.04/ |
| S4 | Microsoft, Remote Development using SSH — https://code.visualstudio.com/docs/remote/ssh |
| S5 | Canonical, image Ubuntu24.04 publiée — https://cloud-images.ubuntu.com/releases/noble/release/ |
| S6 | Pterodactyl, installation Panel et Wings — https://pterodactyl.io/panel/1.0/getting_started.html et https://pterodactyl.io/wings/1.0/installing.html |
| S7 | Docker, installation Ubuntu et filtrage — https://docs.docker.com/engine/install/ubuntu/ et https://docs.docker.com/engine/network/firewall-iptables/ |
| S8 | libvirt, Network Filters — https://libvirt.org/formatnwfilter.html |
| S9 | Rsyslog, templates ; Grafana, Alloy et configuration — https://docs.rsyslog.com/doc/configuration/templates.html et https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.file/ et https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/ |
| S10 | Google, Gmail SMTP et mots de passe d’application — https://support.google.com/mail/answer/7126229 et https://support.google.com/accounts/answer/185833 |
| S11 | Synology, DDNS — https://kb.synology.com/en-global/DSM/help/DSM/AdminCenter/connection_ddns |
| S12 | WireGuard installation et TP-Link ER605W guide WireGuard — https://www.wireguard.com/install/ et https://static.tp-link.com/upload/manual/2025/202505/20250528/1910013938_ER605W%28EU%26US%292.0_UG.pdf |
| S13 | Auteur de minecraft-prometheus-exporter, configuration et métriques — https://github.com/sladkoff/minecraft-prometheus-exporter |
| S14 | CrowdSec, installation et bouncer set-only — https://docs.crowdsec.net/u/getting_started/installation/linux/ et https://docs.crowdsec.net/u/bouncers/firewall/ |
| S15 | Cloudflare, Spectrum et Tunnel TCP — https://developers.cloudflare.com/spectrum/reference/limitations/ et https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/protocols/ |
