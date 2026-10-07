#!/usr/bin/python3
"""Controles locaux sans installation et essais de preparation dans une racine temporaire."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def main():
    files=list(ROOT.rglob('*'))
    for path in files:
        if not path.is_file():continue
        if path.suffix=='.py':ast.parse(path.read_text(),filename=str(path))
        if path.suffix=='.sh' or (path.name in ('Home_server-firewall','Home_server-host-firewall')):
            subprocess.run(['bash','-n',str(path)],check=True)
        if path.suffix=='.json':json.loads(path.read_text())
    prepare=load(ROOT/'scripts/preparer.py','preparer')
    cfg={'pc_ip':'192.168.2.50','nic':'ens3','family_cidr':'192.168.1.0/24',
         'dns_ips':['9.9.9.9','149.112.112.112'],
         'smtp_ips':['8.8.8.8'],'router_syslog_ip':'192.168.5.1'}
    # Valeurs de test uniquement ; ce fichier n'est pas un choix de fournisseur SMTP.
    prepare.validate(cfg)
    for bad in (dict(cfg,nic='ens3; touch /tmp/interdit'),
                dict(cfg,dns_ips=['192.168.2.1','9.9.9.9']),
                dict(cfg,family_cidr='192.168.4.0/24')):
        try:prepare.validate(bad)
        except ValueError:pass
        else:raise AssertionError('Validation negative non appliquee')
    with tempfile.TemporaryDirectory() as td:
        base=Path(td);param=base/'param.json';param.write_text(json.dumps(cfg))
        for role in ('host','game','services'):
            destination=base/role
            subprocess.run([sys.executable,str(ROOT/'scripts/preparer.py'),role,str(param),'--root-dir',str(destination)],check=True,stdout=subprocess.DEVNULL)
            if role=='services':
                env=destination/'opt/Home_server-monitoring/.env';env.write_text('SECRET_A_CONSERVER\n')
                subprocess.run([sys.executable,str(ROOT/'scripts/preparer.py'),role,str(param),'--root-dir',str(destination)],check=True,stdout=subprocess.DEVNULL)
                assert env.read_text()=='SECRET_A_CONSERVER\n'
            for p in destination.rglob('*'):
                if p.is_file() and ('/fichiers/' not in str(p)) and '/exemples/' not in str(p):
                    if p.name not in ('preparer.py','rapport.txt'):
                        # Certains scripts contiennent le detecteur de marqueurs lui-meme.
                        pass
            if role=='game':
                data=(destination/'etc/Home_server-firewall.env').read_text()
                assert '@@' not in data and 'ROLE=game' in data
            other='game' if role!='game' else 'services'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/preparer.py'),other,str(param),'--root-dir',str(destination)],capture_output=True)
            assert result.returncode!=0

        mail=load(ROOT/'fichiers/services/usr/local/sbin/Home_server-mail.py','sender')
        log=base/'alertes.jsonl';rotated=base/'alertes.jsonl.1'
        state={'offsets':{},'count':0,'tags':{},'samples':[]}
        message={'date':'test','tag':'SYSTEME','severity':'3','message':'texte avec " et \\ et retour\nligne'}
        log.write_text(json.dumps(message)+'\n')
        mail.ingest(state,[rotated,log]);assert state['count']==1
        mail.ingest(state,[rotated,log]);assert state['count']==1
        log.rename(rotated);log.write_text(json.dumps(message)+'\n')
        mail.ingest(state,[rotated,log]);assert state['count']==2
        with log.open('a') as f:f.write('{"date":')
        mail.ingest(state,[rotated,log]);assert state['count']==2
        with log.open('a') as f:f.write('"test","tag":"SYSTEME","severity":"3","message":"suite"}\n')
        mail.ingest(state,[rotated,log]);assert state['count']==3
        log.unlink()
        try:mail.ingest(state,[rotated,log])
        except RuntimeError:pass
        else:raise AssertionError("Journal absent non signale")
        log.write_text("[]\n")
        try:mail.ingest({"offsets":{},"count":0,"tags":{},"samples":[]},[log])
        except ValueError:pass
        else:raise AssertionError("Evenement JSON invalide non signale")
        # Verifier TLS obligatoire et verification du nom, sans connexion reseau.
        events=[]
        class SMTP:
            def __init__(self,*args,**kwargs):events.append('connect')
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def ehlo(self):events.append('ehlo')
            def starttls(self,context):
                assert context.check_hostname and context.verify_mode==mail.ssl.CERT_REQUIRED
                events.append('tls')
            def login(self,*args):assert 'tls' in events;events.append('login')
            def send_message(self,msg):assert 'login' in events;events.append('send')
        mail.smtplib.SMTP=SMTP
        mail.deliver({'host':'test.invalid','user':'u','password':'p','from':'a@test.invalid','to':'b@test.invalid'},state)
        assert events[-1]=='send'
    print('Controles statiques, refus de parametres, conservation des secrets, rotation et TLS : conformes.')
    print('Les tests reseau, applicatifs et materiels du document restent a executer.')

if __name__=='__main__':main()
