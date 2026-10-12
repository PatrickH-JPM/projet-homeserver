HOME_SERVER MONITORING V4 - COLLECTE + DASHBOARDS

But:
- rafraîchissement Grafana 2 s;
- métriques Linux/Minecraft réellement mises à jour toutes les ~2 s;
- CPU/RAM/disque/réseau/uptime exacts du conteneur Minecraft via Docker;
- snapshot conntrack toutes les ~2 s pour le graphe historique;
- liste des IP publiques réellement ESTABLISHED/ASSURED visibles par les Linux;
- état des pare-feu/services;
- collecteur SNMP ER605 préparé;
- Grafana reste à 768 MiB dans compose.yaml.

Déploiement:
Le même dossier peut être copié sur les trois machines. Exécuter `sudo ./apply.sh` sur:
1. home-server
2. home-server-mc
3. home-server-services
Le script lit /etc/Home_server-role et n'installe que ce qui correspond au rôle.

ER605 / SNMP:
Le collecteur est installé sur home-server-services mais reste désactivé tant que
/etc/Home_server-er605-snmp.json contient enabled=false ou community=CHANGE_ME.
Il ne faut PAS mettre une vraie communauté SNMP dans Git.
Quand SNMP read-only sera activé sur l'ER605:
- installer le client Net-SNMP: `sudo apt-get install -y snmp`
- éditer /etc/Home_server-er605-snmp.json
- mettre enabled=true et la communauté read-only choisie
- `sudo systemctl restart Home_server-er605-snmp.timer`
Le collecteur essaie d'abord les MIB publiques UCD-SNMP/HOST-RESOURCES puis les OID TP-Link SysMonitor en repli.
Les OID réellement disponibles sur ER605 v2 firmware 2.4.5 devront être validés par snmpwalk.

Conntrack:
AUCUN log n'est filtré ou supprimé. Home_server-conntrack.py ajoute uniquement des métriques agrégées.
La liste des IP externes n'inclut que TCP ESTABLISHED / UDP ASSURED afin de ne pas transformer chaque scan Internet en série Prometheus.

WireGuard:
La métrique actuelle indique les pairs 10.10.10.x vus dans les tables conntrack Linux.
L'état exact du tunnel (handshake, connecté, RX/TX) nécessite encore une source ER605 dédiée.

Consoles Grafana:
- requête initiale limitée aux 500 lignes les plus récentes pour éviter de refaire tomber Grafana;
- affichage Ascending = ancien en haut, nouveau en bas;
- requête Loki direction=backward = on récupère bien les DERNIÈRES lignes;
- infinite scrolling + controls activés pour remonter l'historique disponible.

À traiter séparément:
- rejet IGMP/multicast ER605 -> Home_server: analyse à la source; aucun masquage Grafana;
- acquittement manuel des alertes: plus tard;
- V3 normaliseur: aucune suppression, une ligne brute non vide -> un événement normalisé + raw;
- état WireGuard exact depuis l'ER605;
- validation SNMP CPU/RAM sur l'ER605 v2 2.4.5.
