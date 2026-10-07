#!/bin/bash
set -euo pipefail
role=$(cat /etc/Home_server-role)
echo "Machine : $role"
ip -br addr
if [[ $role == host ]]; then
 sudo nft list table inet Home_server_host
 sudo virsh -c qemu:///system list --all
else
 sudo iptables-legacy -S DOCKER-USER
 sudo iptables-legacy -S PJ-OUT
 sudo systemctl is-active Home_server-firewall docker
fi
echo 'Ces controles ne prouvent pas la segmentation ER605. Executer la recette du guide.'
