#!/usr/bin/python3
"""Tests de parsing/normalisation sans dépendance externe."""
import importlib.util, json, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'usr/local/sbin/Home_server-events-v2.py'
spec=importlib.util.spec_from_file_location('events_v2',MOD)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

samples=[
    '<30>1 2026-10-06T23:02:24+02:00 home-server systemd 1 - -  Finished Home_server-etat.service - Mesure locale des services et conteneurs.',
    '<4>1 2026-10-06T23:02:26+02:00 home-server-mc kernel - - -  FW-SERVEUR-IN IN=ens3 OUT= MAC=x SRC=8.8.8.8 DST=192.168.4.10 LEN=60 PROTO=TCP SPT=54126 DPT=49150 SYN',
    '<30>Oct  6 23:02:26 Home_server-NETFLOW[2949]: [1.0]#011 [NEW] ipv4 2 tcp 6 120 SYN_SENT src=127.0.0.1 dst=127.0.0.1 sport=49426 dport=8081 [UNREPLIED]',
    '<38>1 2026-10-06T23:05:00+02:00 home-server sshd 100 - -  Accepted publickey for patrick from 10.10.10.2 port 50000 ssh2',
]
for s in samples:
    p=m.parse_raw(s)
    assert p['date'] and p['heure'] and p['message']

for rel in ('config.json','identities.json','rules.json','mail-policy.json'):
    json.loads((ROOT/'etc/Home_server-events-v2'/rel).read_text())

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    cfg=json.loads((ROOT/'etc/Home_server-events-v2/config.json').read_text())
    cfg['output_log']=str(td/'v2.jsonl')
    cfg['state_file']=str(td/'state.json')
    e=m.Engine(cfg, json.loads((ROOT/'etc/Home_server-events-v2/identities.json').read_text()), {'rules':[]})
    e.process(samples[0])
    e.process(samples[1])
    e.process(samples[1])
    e.process(samples[3])
    rows=[json.loads(x) for x in (td/'v2.jsonl').read_text().splitlines()]
    assert rows[0]['source']=='server' and rows[0]['type']=='supervision.check.ok'
    assert rows[1]['type']=='firewall.denied' and rows[1]['niveau']=='INFO' and rows[1]['count']==1
    assert rows[2]['type']=='firewall.denied' and rows[2]['niveau']=='ALERTE' and rows[2]['count']==2
    assert rows[3]['type']=='ssh.login.known_ip' and 'PC-Grenoble' in rows[3]['message']

print('Tests V2 OK')
