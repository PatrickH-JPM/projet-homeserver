#!/usr/bin/env bash
set -euo pipefail

ROLE="$(cat /etc/Home_server-role 2>/dev/null || echo unknown)"
OUT="/tmp/Home_server_snapshot_${ROLE}"

sudo rm -rf "$OUT"
sudo mkdir -p "$OUT/files" "$OUT/state"
sudo chown -R "$(id -u):$(id -g)" "$OUT"
sudo chown -R "$(id -u):$(id -g)" "$OUT"

copy_path() {
    local p="$1"
    if [[ -e "$p" ]]; then
        sudo cp -a --parents "$p" "$OUT/files/"
    fi
}

copy_glob() {
    local pattern="$1"
    shopt -s nullglob
    for p in $pattern; do
        copy_path "$p"
    done
    shopt -u nullglob
}

echo "=== Snapshot Home_server : role=$ROLE ==="

# ------------------------------------------------------------
# CONFIGURATION COMMUNE
# ------------------------------------------------------------

copy_path /etc/Home_server-role
copy_path /etc/netplan/20-Home_server.yaml
copy_path /etc/docker/daemon.json
copy_path /etc/ssh/sshd_config

copy_glob "/etc/ssh/sshd_config.d/*.conf"
copy_glob "/etc/rsyslog.d/*Home_server*"
copy_glob "/etc/systemd/system/Home_server-*"
copy_glob "/etc/systemd/journald.conf.d/*Home_server*"
copy_glob "/etc/logrotate.d/*Home_server*"
copy_glob "/etc/cron.d/Home_server*"
copy_glob "/usr/local/sbin/Home_server-*"
copy_glob "/usr/local/bin/Home_server-*"

# Drop-ins systemd liés au projet
while IFS= read -r p; do
    copy_path "$p"
done < <(
    sudo find /etc/systemd/system \
        -type f \
        -path '*Home_server*' \
        2>/dev/null || true
)

# Scripts du projet V8 s'ils existent
if [[ -d /usr/local/lib/Home_server-v8 ]]; then
    while IFS= read -r p; do
        copy_path "$p"
    done < <(
        sudo find /usr/local/lib/Home_server-v8 -type f \
        \( -name '*.sh' -o -name '*.py' -o -name '*.conf' \
           -o -name '*.service' -o -name '*.timer' \
           -o -name '*.yaml' -o -name '*.yml' -o -name '*.json' \) \
        2>/dev/null
    )
fi

# Certificats publics uniquement
copy_glob "/etc/Home_server-pki/*.crt"

# ------------------------------------------------------------
# FIREWALL : configuration sans secrets
# ------------------------------------------------------------

if [[ -f /etc/Home_server-firewall.env ]]; then
    sudo mkdir -p "$OUT/files/etc"
    sudo sed -E \
        '/(PASSWORD|PASS|SECRET|TOKEN|PRIVATE|API.?KEY)/I s/=.*/=<REDACTED>/' \
        /etc/Home_server-firewall.env \
        | sudo tee "$OUT/files/etc/Home_server-firewall.env" >/dev/null
fi

# ------------------------------------------------------------
# VM SERVICES / LOGS
# ------------------------------------------------------------

if [[ "$ROLE" == "services" ]]; then

    # Stack monitoring
    if [[ -d /opt/Home_server-monitoring ]]; then
        sudo mkdir -p "$OUT/files/opt"

        sudo rsync -a \
            --exclude='.env' \
            --exclude='*.db' \
            --exclude='data/' \
            /opt/Home_server-monitoring/ \
            "$OUT/files/opt/Home_server-monitoring/"
    fi

    # NGINX
    copy_glob "/etc/nginx/sites-available/*"
    copy_glob "/etc/nginx/sites-enabled/*"
    copy_glob "/etc/nginx/conf.d/*"

    # CrowdSec : uniquement les règles/configs non secrètes
    copy_path /etc/crowdsec/acquis.yaml
    copy_path /etc/crowdsec/profiles.yaml
    copy_glob "/etc/crowdsec/acquis.d/*.yaml"

    # Pterodactyl : pas de .env
    if [[ -d /var/www/pterodactyl ]]; then
        sudo mkdir -p "$OUT/state"
        cd /var/www/pterodactyl
        {
            echo "Pterodactyl présent"
            [[ -f composer.json ]] && grep '"version"' composer.json || true
        } | sudo tee "$OUT/state/pterodactyl.txt" >/dev/null
    fi
fi

# ------------------------------------------------------------
# VM MINECRAFT / WINGS
# ------------------------------------------------------------

if [[ "$ROLE" == "game" ]]; then

    # On ne copie PAS config.yml de Wings :
    # il peut contenir des credentials/API tokens.
    if command -v wings >/dev/null 2>&1; then
        wings --version 2>&1 \
            | sudo tee "$OUT/state/wings-version.txt" >/dev/null || true
    fi

    # Pas de monde Minecraft, pas de serveur complet.
    # Inventaire uniquement.
    sudo find /var/lib/pterodactyl/volumes \
        -maxdepth 2 -type d 2>/dev/null \
        | sudo tee "$OUT/state/pterodactyl-volumes.txt" >/dev/null || true
fi

# ------------------------------------------------------------
# ÉTAT DU SYSTÈME
# ------------------------------------------------------------

uname -a \
    | sudo tee "$OUT/state/uname.txt" >/dev/null

cat /etc/os-release \
    | sudo tee "$OUT/state/os-release.txt" >/dev/null

timedatectl \
    | sudo tee "$OUT/state/timedatectl.txt" >/dev/null

dpkg-query -W -f='${Package}\t${Version}\n' \
    | sudo tee "$OUT/state/packages.tsv" >/dev/null

ip -br addr \
    | sudo tee "$OUT/state/ip-addresses.txt" >/dev/null

ip route \
    | sudo tee "$OUT/state/routes.txt" >/dev/null

systemctl list-unit-files 'Home_server*' --no-pager \
    | sudo tee "$OUT/state/Home_server-units.txt" >/dev/null

systemctl list-timers --all --no-pager \
    | grep -i Home_server \
    | sudo tee "$OUT/state/Home_server-timers.txt" >/dev/null || true

sudo ss -lntup \
    | sudo tee "$OUT/state/listening-ports.txt" >/dev/null

# ------------------------------------------------------------
# DOCKER
# ------------------------------------------------------------

if command -v docker >/dev/null 2>&1; then

    sudo docker version \
        | sudo tee "$OUT/state/docker-version.txt" >/dev/null

    sudo docker ps -a \
        --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' \
        | sudo tee "$OUT/state/docker-containers.txt" >/dev/null

    sudo docker images --digests \
        | sudo tee "$OUT/state/docker-images.txt" >/dev/null
fi

# ------------------------------------------------------------
# CROWDSEC
# ------------------------------------------------------------

if command -v cscli >/dev/null 2>&1; then

    sudo cscli version \
        | sudo tee "$OUT/state/crowdsec-version.txt" >/dev/null || true

    sudo cscli collections list \
        | sudo tee "$OUT/state/crowdsec-collections.txt" >/dev/null || true

    sudo cscli parsers list \
        | sudo tee "$OUT/state/crowdsec-parsers.txt" >/dev/null || true
fi

# ------------------------------------------------------------
# HÔTE PHYSIQUE / LIBVIRT
# ------------------------------------------------------------

if [[ "$ROLE" == "host" ]]; then

    sudo virsh list --all \
        | sudo tee "$OUT/state/libvirt-vms.txt" >/dev/null

    while IFS= read -r vm; do
        [[ -z "$vm" ]] && continue

        sudo virsh dumpxml "$vm" \
            > "$OUT/state/${vm}.xml"

        sudo virsh dominfo "$vm" \
            > "$OUT/state/${vm}-info.txt"

        sudo virsh domblklist "$vm" \
            > "$OUT/state/${vm}-disks.txt"

        sudo virsh domiflist "$vm" \
            > "$OUT/state/${vm}-interfaces.txt"

    done < <(sudo virsh list --all --name)

    if command -v nft >/dev/null 2>&1; then
        sudo nft list ruleset \
            > "$OUT/state/nft-ruleset.txt"
    fi
fi

# ------------------------------------------------------------
# IPTABLES
# ------------------------------------------------------------

if command -v iptables-save >/dev/null 2>&1; then
    sudo iptables-save \
        > "$OUT/state/iptables-current.txt"
fi

# ------------------------------------------------------------
# SUPPRESSION DÉFENSIVE DE SECRETS
# ------------------------------------------------------------

sudo find "$OUT" -type f \( \
    -iname '*.key' \
    -o -iname '*.pem' \
    -o -iname '*.p12' \
    -o -iname '*.pfx' \
    -o -iname '*private*' \
    -o -name '.env' \
    -o -name 'credentials.yaml' \
    -o -name 'credentials.yml' \
    -o -name 'secrets.json' \
    \) -delete

# Recherche de motifs suspects dans le snapshot
sudo grep -RniE \
    --exclude=POTENTIAL-SECRETS.txt \
    'password|passwd|secret|token|private.?key|api.?key|BEGIN .*PRIVATE' \
    "$OUT" \
    > "$OUT/state/POTENTIAL-SECRETS.txt" || true

sudo chown -R "$(id -u):$(id -g)" "$OUT"

tar -C /tmp \
    -czf "/tmp/Home_server_snapshot_${ROLE}.tar.gz" \
    "Home_server_snapshot_${ROLE}"

echo
echo "Snapshot terminé."
echo "Archive : /tmp/Home_server_snapshot_${ROLE}.tar.gz"
echo "Contrôle secrets : $OUT/state/POTENTIAL-SECRETS.txt"