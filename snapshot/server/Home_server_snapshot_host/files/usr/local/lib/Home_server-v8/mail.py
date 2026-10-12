#!/usr/bin/env python3
import getpass,json,os,socket,subprocess
from pathlib import Path
if os.geteuid()!=0 or Path('/etc/Home_server-role').read_text().strip()!='services':raise SystemExit('Executer sur Home_server_services avec sudo')
p=Path('/etc/Home_server-mail/config.json')
print('Gmail: smtp.gmail.com ; utiliser un mot de passe d application, pas le mot de passe principal.')
host=input('Serveur SMTP [smtp.gmail.com]: ').strip() or 'smtp.gmail.com'
user=input('Adresse de messagerie expediteur: ').strip()
target=input('Adresse destinataire: ').strip()
password=getpass.getpass('Mot de passe d application (masque): ')
cfg={'host':host,'user':user,'password':password,'from':user,'to':target}
p.write_text(json.dumps(cfg,indent=2)+'\n');p.chmod(0o640)
subprocess.run(['chown','root:Home_servermail',str(p)],check=True)
ips=sorted({v[4][0] for v in socket.getaddrinfo(host,587,family=socket.AF_INET,type=socket.SOCK_STREAM)})
params=Path('/etc/Home_server-deploiement/parametres.json');v=json.loads(params.read_text());v['smtp_ips']=ips;params.write_text(json.dumps(v,indent=2)+'\n')
# Only update permitted SMTP destinations; no application rewrite.
env=Path('/etc/Home_server-firewall.env');lines=env.read_text().splitlines();env.write_text('\n'.join('SMTP_IPS="'+' '.join(ips)+'"' if x.startswith('SMTP_IPS=') else x for x in lines)+'\n')
subprocess.run(['/usr/local/sbin/Home_server-firewall'],check=True)
print('SMTP configure. IP a autoriser sur ER605 en TCP 587:',', '.join(ips))
