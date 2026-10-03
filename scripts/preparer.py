#!/usr/bin/python3
"""Copie explicite des fichiers relus. Ne demarre aucun service."""
import argparse
import grp
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil

REPO=Path(__file__).resolve().parents[1]

def validate(cfg):
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}',cfg['nic']):
        raise ValueError('Interface invalide')
    family=ipaddress.IPv4Network(cfg['family_cidr'],strict=True)
    for net in ('192.168.2.0/24','192.168.4.0/24','192.168.3.0/24','192.168.5.0/24','10.10.10.0/24','172.18.0.0/16'):
        if family.overlaps(ipaddress.IPv4Network(net)):
            raise ValueError('Conflit entre reseau familial et plan interne')
    if len(cfg['dns_ips'])!=2:
        raise ValueError('Deux DNS sont requis')
    for value in cfg['dns_ips']+cfg['smtp_ips']:
        if not ipaddress.IPv4Address(value).is_global:
            raise ValueError('DNS et SMTP doivent etre des IPv4 publiques')
    ipaddress.IPv4Address(cfg['router_syslog_ip'])
    pc=ipaddress.IPv4Address(cfg['pc_ip'])
    if pc not in ipaddress.IPv4Network('192.168.2.0/24'):
        raise ValueError('PC administrateur hors VLAN2')
    return {'NIC':cfg['nic'],'FAMILY_CIDR':str(family),
      'DNS1':cfg['dns_ips'][0],'DNS2':cfg['dns_ips'][1],
      'SMTP_IPS':' '.join(cfg['smtp_ips']),
      'ROUTER_SYSLOG_IP':cfg['router_syslog_ip'],
      'PC_IP':str(pc),
      'ADM_GID':str(grp.getgrnam('adm').gr_gid)}

def substitute(text,values):
    for key,value in values.items():
        text=text.replace('@@'+key+'@@',value)
    if re.search(r'@@[A-Z0-9_]+@@',text):
        raise ValueError('Parametre de template non remplace')
    return text

def write(target,text,mode):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_symlink():
        raise ValueError('Destination symbolique refusee')
    # Sous /, la preparation est executee par root et produit des fichiers root.
    tmp=target.with_name(target.name+'.Home_server-tmp')
    if tmp.is_symlink():
        raise ValueError('Destination temporaire symbolique refusee')
    tmp.write_text(text)
    os.chmod(tmp,mode)
    os.replace(tmp,target)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('role',choices=('host','game','services'))
    p.add_argument('parametres',type=Path)
    p.add_argument('--root-dir',type=Path,default=Path('/'),help='Racine de test, sans activation')
    args=p.parse_args()
    root=args.root_dir.resolve()
    if root==Path('/') and os.geteuid()!=0:
        raise SystemExit('Executer avec sudo')
    cfg=json.loads(args.parametres.read_text())
    values=validate(cfg)
    rolefile=root/'etc/Home_server-role'
    if rolefile.exists() and rolefile.read_text().strip()!=args.role:
        raise SystemExit('Cette machine possede deja un autre role')
    manifest=json.loads((REPO/'manifest.json').read_text())
    rendered=[]
    for entry in manifest:
        if entry['role']!=args.role:
            continue
        src=REPO/entry['source']
        if not src.resolve().is_relative_to(REPO) or src.is_symlink():
            raise ValueError('Source hors depot')
        text=substitute(src.read_text(),values)
        dest=entry['destination']
        if entry['stage']:
            dest='/root/Home_server-a-valider/'+Path(dest).name
        rendered.append((root/dest.lstrip('/'),text,int(entry['mode'],8)))
    # Toutes les substitutions sont verifiees avant la premiere copie.
    write(rolefile,args.role+'\n',0o644)
    for target,text,mode in rendered:
        write(target,text,mode)
    scriptdir=root/'usr/local/lib/Home_server-v8'
    scriptdir.mkdir(parents=True,exist_ok=True)
    for source in (REPO/'scripts').iterdir():
        if source.is_file() and source.suffix in ('.sh','.py'):
            write(scriptdir/source.name,source.read_text(),0o750)
    ex=root/'etc/Home_server-deploiement/exemples'
    for source in (REPO/'exemples').iterdir():
        if source.is_file():
            text=source.read_text()
            # Les exemples non rendus restent explicitement des fragments.
            if source.name=='monitoring.env':
                text=substitute(text,values)
            write(ex/source.name,text,0o600)
    if args.role=='services':
        env=root/'opt/Home_server-monitoring/.env'
        if not env.exists():
            write(env,substitute((REPO/'exemples/monitoring.env').read_text(),values),0o600)
        mail=root/'etc/Home_server-mail/config.json'
        if not mail.exists():
            write(mail,(REPO/'exemples/mail-config.json').read_text(),0o640)
    report=root/'root/Home_server-a-valider/rapport.txt'
    write(report,'Role '+args.role+'\n'+'\n'.join(str(t) for t,_,_ in rendered)+'\n',0o600)
    print('Preparation terminee pour '+args.role+'. Relire /root/Home_server-a-valider/rapport.txt.')

if __name__=='__main__':
    main()
