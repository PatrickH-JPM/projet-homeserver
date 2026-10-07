#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 && $(cat /etc/Home_server-role) == services ]]
[[ -s /var/www/pterodactyl/artisan && ! -e /etc/Home_server-deploiement/panel-initialise ]]
cd /var/www/pterodactyl
systemctl start mariadb redis-server php8.3-fpm
secret=$(openssl rand -hex 24)
# Random hexadecimal secret: no SQL interpolation from user input.
printf "CREATE DATABASE panel; CREATE USER 'pterodactyl'@'127.0.0.1' IDENTIFIED BY '%s'; GRANT ALL PRIVILEGES ON panel.* TO 'pterodactyl'@'127.0.0.1';\n" "$secret" | mariadb
export HOME_SERVER_DB_SECRET=$secret
python3 - <<'PY'
import os,re
from pathlib import Path
p=Path('.env');s=p.read_text();values={'APP_URL':'https://panel.home.arpa','APP_ENV':'production','APP_DEBUG':'false','DB_HOST':'127.0.0.1','DB_PORT':'3306','DB_DATABASE':'panel','DB_USERNAME':'pterodactyl','DB_PASSWORD':os.environ['HOME_SERVER_DB_SECRET'],'REDIS_HOST':'127.0.0.1','CACHE_DRIVER':'redis','SESSION_DRIVER':'redis','QUEUE_CONNECTION':'redis','MAIL_MAILER':'log','TRUSTED_PROXIES':'127.0.0.1'}
for key,value in values.items():
 line=key+'='+value
 if re.search(r'^'+key+'=',s,re.M):s=re.sub(r'^'+key+r'=.*$',line,s,flags=re.M)
 else:s+='\n'+line
p.write_text(s+'\n')
PY
unset HOME_SERVER_DB_SECRET secret
chown www-data:www-data .env
trap 'chown root:www-data /var/www/pterodactyl/.env; chmod 0640 /var/www/pterodactyl/.env' EXIT
sudo -u www-data php artisan key:generate --force
sudo -u www-data php artisan migrate --seed --force
sudo -u www-data php artisan p:user:make
touch /etc/Home_server-deploiement/panel-initialise
printf 'Compte cree. URL : https://panel.home.arpa\n'
