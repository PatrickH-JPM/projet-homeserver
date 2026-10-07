#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Executer avec sudo." >&2; exit 1; }
timedatectl set-timezone Europe/Paris
timedatectl set-ntp true
printf '\nConfiguration horaire :\n'
timedatectl status
