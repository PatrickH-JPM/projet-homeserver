# Intégration au dépôt V8

Ajouter au manifest, pour les rôles `host`, `game`, `services` :

- `/usr/local/sbin/Home_server-etat.py`
- `/usr/local/sbin/Home_server-conntrack.py`
- `/etc/systemd/system/Home_server-etat.service`
- `/etc/systemd/system/Home_server-etat.timer`
- `/etc/systemd/system/Home_server-conntrack.service`
- `/etc/systemd/system/Home_server-conntrack.timer`

Pour `services` uniquement :

- `/usr/local/sbin/Home_server-er605-snmp.py`
- `/etc/systemd/system/Home_server-er605-snmp.service`
- `/etc/systemd/system/Home_server-er605-snmp.timer`
- `/opt/Home_server-monitoring/prometheus.yaml`
- `/opt/Home_server-monitoring/compose.yaml`
- les trois dashboards JSON du dossier `services/opt/Home_server-monitoring/dashboards/`

Ne pas versionner `/etc/Home_server-er605-snmp.json` s'il contient une communauté SNMP réelle.
Le fichier `.example` peut être versionné.

Le `source/monitoring.sh` fourni corrige également le `docker events --format` en le passant comme un seul argument et active les nouveaux timers.
