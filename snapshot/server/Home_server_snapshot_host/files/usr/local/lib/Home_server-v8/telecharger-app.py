#!/usr/bin/env python3
import hashlib,json,os,urllib.request
from pathlib import Path
if os.geteuid()!=0:raise SystemExit('Executer avec sudo')
role=Path('/etc/Home_server-role').read_text().strip()
if role not in ('game','services'):raise SystemExit('VM attendue')
repo='pterodactyl/wings' if role=='game' else 'pterodactyl/panel'
asset='wings_linux_amd64' if role=='game' else 'panel.tar.gz'
filename='wings' if role=='game' else asset
req=urllib.request.Request('https://api.github.com/repos/'+repo+'/releases/latest',headers={'User-Agent':'Home_server-v8'})
release=json.load(urllib.request.urlopen(req,timeout=30))
version=release['tag_name'].lstrip('v')
parts=tuple(int(p) for p in version.split('.')[:3])
if parts<(1,12,0) or release.get('prerelease'):raise SystemExit('Version non admise')
items=[a for a in release['assets'] if a['name']==asset]
if len(items)!=1:raise SystemExit('Asset officiel absent')
a=items[0];url=a['browser_download_url']
if not url.startswith('https://github.com/'+repo+'/releases/'):raise SystemExit('URL inattendue')
p=Path('/etc/Home_server-deploiement')/filename
if p.exists():raise SystemExit('Telechargement deja present; version conservee')
urllib.request.urlretrieve(url,str(p)+'.part');data=Path(str(p)+'.part').read_bytes();digest=hashlib.sha256(data).hexdigest()
if a.get('digest') and a['digest']!='sha256:'+digest:raise SystemExit('Empreinte GitHub incorrecte')
Path(str(p)+'.part').replace(p);(p.parent/('wings.sha256' if role=='game' else 'panel.sha256')).write_text(digest+'  '+filename+'\n')
(p.parent/(filename+'.version')).write_text(release['tag_name']+'\n'+url+'\n'+digest+'\n')
print('Version telechargee:',release['tag_name'])
