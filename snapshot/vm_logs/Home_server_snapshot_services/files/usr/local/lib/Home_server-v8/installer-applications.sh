#!/bin/bash
set -euo pipefail
[[ $EUID -eq 0 ]]
ROLE=${1:?role requis}
[[ "$ROLE" == "$(cat /etc/Home_server-role)" ]]
cd /etc/Home_server-deploiement
if [[ "$ROLE" == game ]]; then
  [[ -s wings && -s wings.sha256 ]]
  # Le fichier somme doit nommer exactement wings, pas un chemin arbitraire.
  python3 - <<'PY'
import hashlib,re
from pathlib import Path
expected=Path('wings.sha256').read_text().strip()
if not re.fullmatch(r'[0-9a-f]{64}  wings',expected):
    raise SystemExit('Format attendu : empreinte SHA256 puis deux espaces puis wings')
assert hashlib.sha256(Path('wings').read_bytes()).hexdigest()==expected.split()[0]
PY
  [[ ! -e /usr/local/bin/wings ]] || { echo 'Wings deja present ; utiliser la procedure de mise a jour.'; exit 1; }
  install -m 0755 wings /usr/local/bin/wings
  install -d -m 0700 /etc/pterodactyl
  echo 'Wings installe. Configuration complete et certificats encore requis.'
elif [[ "$ROLE" == services ]]; then
  [[ -s panel.tar.gz && -s panel.sha256 ]]
  [[ ! -e /var/www/pterodactyl/artisan ]] || { echo 'Panel deja present ; initialisation refusee.'; exit 1; }
  install -d -m 0755 /var/www/pterodactyl
  python3 - <<'PY'
import hashlib,re,tarfile
from pathlib import Path
expected=Path('panel.sha256').read_text().strip()
if not re.fullmatch(r'[0-9a-f]{64}  panel.tar.gz',expected):
    raise SystemExit('Format attendu : SHA256 puis deux espaces puis panel.tar.gz')
assert hashlib.sha256(Path('panel.tar.gz').read_bytes()).hexdigest()==expected.split()[0]
with tarfile.open('panel.tar.gz') as archive:
    archive.extractall('/var/www/pterodactyl',filter='data')
PY
  chown -R www-data:www-data /var/www/pterodactyl
  cd /var/www/pterodactyl
  [[ -s artisan && -s composer.lock ]]
  [[ -e .env ]] || sudo -u www-data cp .env.example .env
  sudo -u www-data composer install --no-dev --optimize-autoloader --no-interaction
  chown -R root:root /var/www/pterodactyl
  chown -R www-data:www-data storage bootstrap/cache
  chown root:www-data .env
  chmod 0640 .env
  chmod -R u+rwX,g+rwX,o-rwx storage bootstrap/cache
  echo 'Panel installe. Base, APP_KEY, assistants et compte initial encore requis.'
else
  echo 'Aucune application sur l hyperviseur.'
fi
