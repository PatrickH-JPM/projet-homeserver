#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 && $(cat /etc/Home_server-role) == host ]]
[[ -s /root/Home_server-a-valider/20-Home_server.yaml ]]
echo 'Executer uniquement sur le clavier/ecran de Home_server. Cette operation modifie son reseau.'
read -r -p 'Saisir CONSOLE pour continuer : ' confirmation
[[ $confirmation == CONSOLE ]]
backup_dir=/root/Home_server-netplan-original
[[ ! -e $backup_dir ]] || { echo 'Configuration deja migree. Reexecution refusee.'; exit 1; }
install -d -m 0700 "$backup_dir"
shopt -s nullglob
for f in /etc/netplan/*.yaml; do mv "$f" "$backup_dir/"; done
install -m 0600 /root/Home_server-a-valider/20-Home_server.yaml /etc/netplan/20-Home_server.yaml
mkdir -p /etc/cloud/cloud.cfg.d
printf 'network: {config: disabled}\n' > /etc/cloud/cloud.cfg.d/99-Home_server-network.cfg
if ! netplan generate; then
 rm /etc/netplan/20-Home_server.yaml
 for f in "$backup_dir"/*.yaml; do mv "$f" /etc/netplan/; done
 exit 1
fi
netplan apply
hostnamectl set-hostname home-server
hostnamectl --pretty set-hostname Home_server
systemctl daemon-reload
systemctl enable --now Home_server-host-firewall.service
# Covers monolithic and modular installations; libvirt owns its own filters.
for svc in libvirtd virtqemud virtqemud.socket libvirt-guests; do
 if systemctl cat "$svc" >/dev/null 2>&1; then
  install -d "/etc/systemd/system/$svc.d"
  printf '[Unit]\nRequires=Home_server-host-firewall.service\nAfter=Home_server-host-firewall.service\n' > "/etc/systemd/system/$svc.d/20-Home_server-firewall.conf"
 fi
done
systemctl daemon-reload
printf 'Reseau applique. Depuis le PC gamer: ssh patrick@192.168.3.10\n'
