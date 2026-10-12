#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]]
ROLE=${1:?role requis}
[[ "$ROLE" == "$(cat /etc/Home_server-role)" ]]
source /etc/os-release
[[ "$ID" == ubuntu && ( "$VERSION_ID" == 24.04 || "$VERSION_ID" == 26.04 ) ]]
apt-get update
apt-get install -y openssh-server rsyslog chrony python3 python3-yaml acl curl ca-certificates \
  prometheus-node-exporter logrotate
install -d -m 0755 /var/lib/Home_server-textfile
install -d -m 0750 -o syslog -g syslog /var/spool/rsyslog
install -d -m 0750 /etc/Home_server-pki
install -d -m 0755 /etc/systemd/system/prometheus-node-exporter.service.d
LISTEN=127.0.0.1
if [[ "$ROLE" == host ]]; then
  apt-get install -y qemu-kvm libvirt-daemon-system libvirt-clients virtinst cpu-checker nftables
  LISTEN=192.168.3.10
  sysctl -p /etc/sysctl.d/70-Home_server.conf
  systemctl disable ufw.service nftables.service 2>/dev/null || true
else
  apt-get install -y iptables ipset
  update-alternatives --set iptables /usr/sbin/iptables-legacy
  update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy
  systemctl disable --now ufw.service 2>/dev/null || true
  # Ne pas arreter nftables.service, dont ExecStop peut vider les regles.
  systemctl disable nftables.service 2>/dev/null || true
  cat > /etc/sysctl.d/70-Home_server.conf <<'SYSCTL'
net.ipv4.ip_forward=1
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
SYSCTL
  sysctl -p /etc/sysctl.d/70-Home_server.conf
fi
cat > /etc/systemd/system/prometheus-node-exporter.service.d/20-Home_server.conf <<EOF
[Service]
ExecStart=
ExecStart=/usr/bin/prometheus-node-exporter --web.listen-address=$LISTEN:9100 --collector.textfile.directory=/var/lib/Home_server-textfile
EOF
if [[ "$ROLE" == game ]]; then LISTEN=192.168.4.10; fi
if [[ "$ROLE" == game ]]; then
  sed -i 's/127.0.0.1:9100/192.168.4.10:9100/' /etc/systemd/system/prometheus-node-exporter.service.d/20-Home_server.conf
fi
if [[ "$ROLE" == services ]]; then
  apt-get install -y nginx mariadb-server redis-server composer php8.3-cli php8.3-fpm \
    php8.3-gd php8.3-mysql php8.3-mbstring php8.3-bcmath php8.3-xml php8.3-curl php8.3-zip unzip tar
  id Home_servermail >/dev/null 2>&1 || useradd --system --home-dir /var/lib/Home_server-mail --shell /usr/sbin/nologin Home_servermail
  usermod -aG adm Home_servermail
  install -d -m 0700 -o Home_servermail -g Home_servermail /var/lib/Home_server-mail
  install -d -m 0755 -o Home_servermail -g Home_servermail /var/lib/Home_server-mail-public
  chown root:Home_servermail /etc/Home_server-mail/config.json
  chmod 0640 /etc/Home_server-mail/config.json
  install -d -m 0750 -o syslog -g adm /var/log/Home_server
  [[ -e /var/log/Home_server/evenements.jsonl ]] || install -m 0640 -o syslog -g adm /dev/null /var/log/Home_server/evenements.jsonl
  ln -sfn /var/lib/Home_server-mail-public/mail.prom /var/lib/Home_server-textfile/mail.prom
  install -d -m 0750 -o 10001 -g 10001 /var/lib/Home_server-monitoring/loki
  install -d -m 0750 -o 65534 -g 65534 /var/lib/Home_server-monitoring/prometheus
  install -d -m 0750 -o 472 -g 472 /var/lib/Home_server-monitoring/grafana
  install -d -m 0750 -o 473 -g 473 /var/lib/Home_server-monitoring/alloy
  ln -sfn /etc/nginx/sites-available/Home_server /etc/nginx/sites-enabled/Home_server
  rm -f /etc/nginx/sites-enabled/default
fi
# Un seul ensemble de sources NTP, sans fournisseur Cloudflare impose.
[[ -e /etc/chrony/chrony.conf.Home_server-original ]] || cp -a /etc/chrony/chrony.conf /etc/chrony/chrony.conf.Home_server-original
sed -i -E '/^[[:space:]]*(pool|server|peer)[[:space:]]/d' /etc/chrony/chrony.conf
grep -qxF 'pool ntp.ubuntu.com iburst' /etc/chrony/chrony.conf || echo 'pool ntp.ubuntu.com iburst' >> /etc/chrony/chrony.conf
systemctl daemon-reload
if [[ "$ROLE" == host ]]; then
  systemctl enable Home_server-host-firewall.service
else
  systemctl enable Home_server-firewall.service
fi
systemctl enable prometheus-node-exporter.service
echo 'Base installee. Ne pas ouvrir Minecraft avant activation et recette.'

if ! grep -q 'panel.home.arpa' /etc/hosts; then
 printf '\n192.168.5.10 panel.home.arpa grafana.home.arpa wings.home.arpa\n192.168.4.10 wings-game.home.arpa\n' >> /etc/hosts
fi

install -d -m 0755 /etc/ssh/sshd_config.d
printf 'PermitRootLogin no\nPasswordAuthentication yes\nKbdInteractiveAuthentication no\nAllowAgentForwarding no\nAllowUsers patrick\n' > /etc/ssh/sshd_config.d/00-Home_server.conf
/usr/sbin/sshd -t
systemctl reload ssh
