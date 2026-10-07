#!/usr/bin/python3
"""Resume de gravite rsyslog. Pas de dependance a Grafana, aucun shell."""
import argparse
import collections
import fcntl
import json
import os
from pathlib import Path
import smtplib
import ssl
import time
import re
from email.message import EmailMessage

CONFIG=Path('/etc/Home_server-mail/config.json')
STATE=Path('/var/lib/Home_server-mail/state.json')
LOG=Path('/var/log/Home_server/evenements.jsonl')
METRICS=Path('/var/lib/Home_server-mail-public/mail.prom')

def alert_event(obj):
    message=str(obj.get('message',''))
    try:
        severity=int(obj.get('severity',6))
    except (TypeError,ValueError):
        severity=6
    return severity<=3 or bool(re.search(
        r'joined the game|left the game|logged in with entity|Done \(|Stopping server|'
        r'ERROR|Exception|crash|OOM|PROTECTED-|FW-|CS-BLOCK|ban|decision|scan|'
        r'Failed password|Accepted publickey|AUTH|SECURITY|"Action":"(die|oom|kill)"',message,re.I))

def atomic(path,data,mode):
    tmp=path.with_name(path.name+'.tmp')
    with open(tmp,'w',encoding='utf-8') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp,mode)
    os.replace(tmp,path)

def ingest(state,paths):
    paths=list(paths)
    if not paths or not paths[-1].is_file():
        raise RuntimeError("Journal courant absent")
    # Lire la rotation non compressee avant le fichier courant.
    for path in paths:
        if not path.exists():
            continue
        st=path.stat()
        key='%s:%s' % (st.st_dev,st.st_ino)
        pos=state['offsets'].get(key,0)
        if pos>st.st_size:
            raise RuntimeError('Troncature du journal sans rotation valide')
        with open(path,'rb') as f:
            f.seek(pos)
            for _ in range(10000):
                line=f.readline(65537)
                if not line:
                    break
                if not line.endswith(b'\n'):
                    # Garder la derniere ligne incomplete pour le passage suivant.
                    if len(line)>65536:
                        raise RuntimeError('Ligne de journal anormalement longue')
                    break
                obj=json.loads(line)
                if not isinstance(obj,dict):
                    raise ValueError("Evenement JSON non objet")
                state['offsets'][key]=f.tell()
                msg=str(obj.get('message',''))
                flow=re.search(r'src=([0-9.]+) dst=([0-9.]+).*?dport=(\d+)',msg)
                if flow and 'NETFLOW' in str(obj.get('tag','')):
                    now=time.time()
                    scans=state.setdefault('scan_ports',{})
                    scans={k:v for k,v in scans.items() if now-v['start']<60}
                    if len(scans)<1000 or flow[1] in scans:
                        item=scans.setdefault(flow[1],{'start':now,'ports':[]})
                        if flow[3] not in item['ports']:
                            item['ports'].append(flow[3])
                        if len(item['ports'])==20:
                            obj=dict(obj,message='SECURITY scan suspecte '+flow[1]+' : 20 ports distincts en 60 secondes')
                    state['scan_ports']=scans
                if not alert_event(obj):
                    continue
                state['count']+=1
                tag=str(obj.get('tag','SYSTEME'))[:64]
                state['tags'][tag]=state['tags'].get(tag,0)+1
                if len(state['samples'])<20:
                    # Conserver le message comme donnees, jamais comme commande.
                    text=str(obj.get('message',''))[:500]
                    state['samples'].append('%s %s %s' % (obj.get('date',''),tag,text))
                state['offsets'][key]=f.tell()
    live=set()
    for path in paths:
        if path.exists():
            st=path.stat();live.add('%s:%s' % (st.st_dev,st.st_ino))
    state['offsets']={k:v for k,v in state['offsets'].items() if k in live}

def deliver(cfg,state,test=False):
    msg=EmailMessage()
    msg['From']=cfg['from']
    msg['To']=cfg['to']
    msg['Subject']='[Home_server] Test SMTP' if test else '[Home_server] Evenements'
    text='Test de la chaine SMTP avec STARTTLS verifie.' if test else (
        '%d evenements depuis le precedent envoi.\n%s\n\nExtraits non certifies :\n%s' % (
            state['count'],json.dumps(state['tags'],ensure_ascii=False),
            '\n'.join(state['samples'])))
    msg.set_content(text)
    with smtplib.SMTP(cfg['host'],587,timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(cfg['user'],cfg['password'])
        smtp.send_message(msg)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--test',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    with open(STATE.parent/'lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cfg=json.loads(CONFIG.read_text())
        state=json.loads(STATE.read_text()) if STATE.exists() else {
            'offsets':{},'count':0,'tags':{},'samples':[],
            'last_success':0,'last_attempt':0}
        now=time.time();error=0
        try:
            ingest(state,[LOG.with_name(LOG.name+'.1'),LOG])
            atomic(STATE,json.dumps(state),0o600)
            if args.test or (state['count'] and now-state['last_attempt']>=10):
                state['last_attempt']=now
                atomic(STATE,json.dumps(state),0o600)
                deliver(cfg,state,args.test)
                state['last_success']=now
                if not args.test:
                    state.update(count=0,tags={},samples=[])
                atomic(STATE,json.dumps(state),0o600)
        except (OSError,ValueError,RuntimeError,smtplib.SMTPException):
            error=1
            # Pas de secret ni de corps de message dans le journal du service.
            print('Erreur de lecture ou envoi SMTP ; verifier le service et sa configuration.')
        # Le flag d'erreur persiste pendant l'attente de la prochaine tentative.
        if state['count'] and state['last_attempt']>state['last_success']:
            error=1
        atomic(METRICS,'\n'.join([
            'Home_server_mail_check_timestamp_seconds %s' % now,
            'Home_server_mail_error %s' % error,
            'Home_server_mail_pending_events %s' % state['count'],
            'Home_server_mail_last_success_timestamp_seconds %s' % state['last_success']
        ])+'\n',0o644)
        return error

if __name__=='__main__':
    raise SystemExit(main())
