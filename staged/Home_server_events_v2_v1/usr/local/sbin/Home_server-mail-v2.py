#!/usr/bin/python3
"""Envoi SMTP basé uniquement sur les types explicitement autorisés par mail-policy.json."""
import argparse, fcntl, json, os, smtplib, ssl
from email.message import EmailMessage
from pathlib import Path

CONFIG=Path('/etc/Home_server-mail/config.json')
POLICY=Path('/etc/Home_server-events-v2/mail-policy.json')
LOG=Path('/var/log/Home_server/evenements-v2.jsonl')
STATE=Path('/var/lib/Home_server-mail-v2/state.json')
METRICS=Path('/var/lib/Home_server-mail-public/mail-v2.prom')

ORDER={'INFO':0,'ALERTE':1,'CRITIQUE':2}

def atomic(path,text,mode):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(text,encoding='utf-8'); os.chmod(tmp,mode); os.replace(tmp,path)

def allowed(policy, event_type):
    item=policy.get('events',{}).get(event_type)
    return bool(item.get('mail')) if isinstance(item,dict) else bool(policy.get('default',False))

def ingest(state,policy):
    selected=[]
    paths=[LOG.with_name(LOG.name+'.1'),LOG]
    live=set()
    for path in paths:
        if not path.exists(): continue
        st=path.stat(); key=f'{st.st_dev}:{st.st_ino}'; live.add(key)
        pos=int(state.get('offsets',{}).get(key,0))
        if pos>st.st_size: pos=0
        with path.open('rb') as f:
            f.seek(pos)
            for _ in range(10000):
                line=f.readline(65537)
                if not line or not line.endswith(b'\n'): break
                state.setdefault('offsets',{})[key]=f.tell()
                try: e=json.loads(line)
                except ValueError: continue
                if allowed(policy,str(e.get('type',''))): selected.append(e)
    state['offsets']={k:v for k,v in state.get('offsets',{}).items() if k in live}
    return selected

def deliver(cfg,events,test=False):
    msg=EmailMessage(); msg['From']=cfg['from']; msg['To']=cfg['to']
    if test:
        msg['Subject']='[Home_server V2] Test SMTP'
        msg.set_content('Test SMTP Home_server V2. Aucun evenement reel n a ete envoye.')
    else:
        highest=max((e.get('niveau','INFO') for e in events),key=lambda x:ORDER.get(x,0),default='INFO')
        msg['Subject']=f'[Home_server V2] {highest} - {len(events)} evenement(s)'
        body=[]
        for e in events[:50]:
            body.append('{date} {heure} | {source} | {categorie} | [{niveau}] | {message}'.format(**e))
        if len(events)>50: body.append(f'... {len(events)-50} evenement(s) supplementaire(s) non affiches.')
        msg.set_content('\n'.join(body))
    with smtplib.SMTP(cfg['host'],587,timeout=20) as smtp:
        smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo()
        smtp.login(cfg['user'],cfg['password']); smtp.send_message(msg)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--test',action='store_true'); args=ap.parse_args()
    os.umask(0o077); STATE.parent.mkdir(parents=True,exist_ok=True)
    with (STATE.parent/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cfg=json.loads(CONFIG.read_text()); policy=json.loads(POLICY.read_text())
        state=json.loads(STATE.read_text()) if STATE.exists() else {'offsets':{}}
        events=[] if args.test else ingest(state,policy)
        atomic(STATE,json.dumps(state),0o600)
        error=0
        try:
            if args.test or events: deliver(cfg,events,args.test)
        except (OSError,ValueError,smtplib.SMTPException):
            error=1; print('Erreur SMTP Home_server V2.')
        atomic(METRICS,f'Home_server_mail_v2_error {error}\nHome_server_mail_v2_selected_events {len(events)}\n',0o644)
        return error
if __name__=='__main__': raise SystemExit(main())
