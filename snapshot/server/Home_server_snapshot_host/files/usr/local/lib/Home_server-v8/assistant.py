#!/usr/bin/env python3
"""Questions locales uniquement; aucun secret transmis ou publie."""
import ipaddress,json,re,subprocess,sys
from pathlib import Path
role=sys.argv[1] if len(sys.argv)>1 else ''
if role not in ('host','game','services'): raise SystemExit('Role attendu: host, game ou services')
if role!='host':
 osrelease=Path('/etc/os-release').read_text()
 if 'VERSION_ID="24.04"' not in osrelease: raise SystemExit('Les VM Pterodactyl de ce guide utilisent Ubuntu 24.04.')
repo=Path(__file__).resolve().parents[1]
p=Path('/etc/Home_server-deploiement/parametres.json');p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
if p.exists():
 print('Parametres existants conserves:',p)
else:
 links=subprocess.check_output(['ip','-br','link'],text=True)
 print(links)
 candidates=[line.split()[0] for line in links.splitlines() if line.split()[0]!='lo' and not line.split()[0].startswith(('br-','vlan','virbr','docker','veth'))]
 default=candidates[0] if len(candidates)==1 else ''
 nic=input('Nom de la carte reseau ['+default+']: ').strip() or default
 if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}',nic):raise SystemExit('Nom invalide')
 family=str(ipaddress.IPv4Network(input('Reseau LAN de la box (exemple 192.168.1.0/24): ').strip(),strict=True))
 pc=str(ipaddress.IPv4Address(input('IP reservee du PC gamer [192.168.2.50]: ').strip() or '192.168.2.50'))
 cfg={'nic':nic,'family_cidr':family,'pc_ip':pc,'dns_ips':['9.9.9.9','149.112.112.112'],'smtp_ips':[],'router_syslog_ip':'192.168.5.1'}
 p.write_text(json.dumps(cfg,indent=2)+'\n');p.chmod(0o600)
subprocess.run([sys.executable,str(repo/'scripts/preparer.py'),role,str(p)],check=True)
print('Fichiers prepares. Etape suivante: installation de la base, puis activation du pare-feu.')
