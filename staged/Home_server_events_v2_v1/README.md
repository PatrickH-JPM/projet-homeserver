# Home_server — Normaliseur d'événements V2 — v1

## Architecture

La V2 lit **directement** `/var/log/Home_server/brut.log`. Elle ne dépend pas de `evenements.jsonl` V1.
Le brut reste la référence technique exhaustive. La V2 produit `/var/log/Home_server/evenements-v2.jsonl` pour l'affichage humain, Grafana et le futur filtre mail.

Format d'affichage :

`DATE HEURE | SOURCE | CATÉGORIE | [NIVEAU] | MESSAGE HUMAIN`

Sources : `server`, `vm_logs`, `vm_mc`, `ER605`.
Niveaux : `INFO`, `ALERTE`, `CRITIQUE`.

Les couleurs sont ajoutées **uniquement** par `Home_server-journal` : blanc, orange, rouge. Aucun code ANSI n'est écrit dans les journaux. Grafana utilisera plus tard le champ `niveau` pour ses propres couleurs.

## Heure

Avant validation de la V2, régler les trois Linux sur `Europe/Paris` :

```bash
sudo timedatectl set-timezone Europe/Paris
sudo timedatectl set-ntp true
timedatectl status
```

À faire sur : `server`, `vm_mc`, `vm_logs`. Le V2 ne crée pas de champ Unix `timestamp` ; il écrit `date` et `heure` dans le format local.

## Conntrack / réseau

`conntrack -E` reste collecté dans `brut.log`, mais les cycles TCP `NEW → SYN_RECV → ESTABLISHED → FIN_WAIT → CLOSE_WAIT → CLOSE` ne sont pas recopiés dans la V2.

Pour les services connus, ces cycles servent uniquement à détecter un **changement d'état** :

- Minecraft exporter `vm_logs → vm_mc:9940`
- node_exporter `vm_logs → vm_mc:9100`
- node_exporter `vm_logs → server:9100`
- Pterodactyl/Wings `vm_logs → vm_mc:8080`
- CrowdSec LAPI `127.0.0.1:8081`

Une connexion TCP établie prouve que le port répond, **pas le contenu applicatif exact transmis**. Les valeurs TPS/RAM/joueurs resteront du ressort de Prometheus/Grafana.

## Pare-feu

Les préfixes `FW-SERVEUR*`, `FW-DOCKER*` et `FW-HOTE*` sont émis juste avant les DROP dans la configuration actuelle ; la V2 les traduit donc en `Connexion refusée`.

Les vérifications `Home_server-etat` très fréquentes sont ramenées à un heartbeat INFO au plus toutes les 60 s par machine (réglable dans `config.json`). Les répétitions pare-feu utilisent un compteur. Le viewer remplace la dernière ligne à l'écran quand le même événement se répète immédiatement.

La V2 **ne prétend jamais qu'une IP est bannie uniquement parce qu'elle a été refusée plusieurs fois**. `IP bannie et bloquée` n'est émis que lorsqu'un journal CrowdSec confirme réellement un bannissement/blocage.

## IP connues

`identities.json` contient les noms administratifs (`PC-Grenoble`, `PC-Tours`, etc.).
Une première authentification réussie depuis une IP non connue devient `[ALERTE]`, puis l'IP est mémorisée dans l'état V2 et les connexions suivantes deviennent `[INFO]`.

## Extensibilité

- `config.json` : sources, ports, probes, seuils.
- `identities.json` : noms des IP/machines.
- `rules.json` : traductions simples supplémentaires par regex.
- `mail-policy.json` : liste des types d'événements et décision mail oui/non.

Les événements V2 sont structurés (`source`, `categorie`, `niveau`, `type`, `service`, IP/ports, compteur...). Grafana pourra donc afficher le flux complet ou filtrer uniquement `ER605`, `server`, `vm_mc`, `NGINX`, `CrowdSec`, etc.

## Installation sur vm_logs

Copier ce dossier sur `Home_server_services`, puis :

```bash
cd Home_server_events_v2_v1
sudo ./scripts/install-v2.sh
```

Le moteur démarre à la fin de `brut.log` au premier lancement : il ne retraitera pas les milliers de lignes historiques.

Le mail V1 est désactivé par l'installateur et le mail V2 reste **désactivé** tant que `mail-policy.json` n'a pas été validé.

## Affichage

Tout :

```bash
Home_server-journal
```

Uniquement ER605 :

```bash
Home_server-journal --source ER605
```

Uniquement vm_mc :

```bash
Home_server-journal --source vm_mc
```

Uniquement CrowdSec :

```bash
Home_server-journal --category CrowdSec
```

Alertes et critiques :

```bash
Home_server-journal --level ALERTE --level CRITIQUE
```

## Mail V2

Test SMTP uniquement :

```bash
sudo -u Home_servermail /usr/local/sbin/Home_server-mail-v2.py --test
```

Ne pas activer le timer avant validation de `mail-policy.json`.

Quand la politique sera prête :

```bash
sudo systemctl enable --now Home_server-mail-v2.timer
```
