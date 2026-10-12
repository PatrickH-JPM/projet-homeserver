#!/bin/bash
set -u

# Suit la stdout/stderr du conteneur Pterodactyl qui expose Minecraft (49150 ou exporter 9940)
# et la renvoie dans journald/syslog sous le programme mc-serveur.
while true; do
  CID="$(docker ps --format '{{.ID}} {{.Ports}}' 2>/dev/null | awk '/49150|9940/ {print $1; exit}')"
  if [[ -z "$CID" ]]; then
    sleep 1
    continue
  fi

  SINCE="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  docker logs --follow --since "$SINCE" "$CID" 2>&1 | sed -u -E $'s/\x1B\[[0-9;?]*[ -\/]*[@-~]//g; s/\r$//' | logger -t mc-serveur
  sleep 1
done
