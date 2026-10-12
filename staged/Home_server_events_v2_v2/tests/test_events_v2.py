#!/usr/bin/python3
"""Tests de parsing/normalisation V2 v2 sans dépendance externe."""
import importlib.util, json, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'usr/local/sbin/Home_server-events-v2.py'
spec=importlib.util.spec_from_file_location('events_v2',MOD)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

samples={
    'etat':'<30>1 2026-10-06T23:02:24+02:00 home-server systemd 1 - -  Finished Home_server-etat.service - Mesure locale des services et conteneurs.',
    'fw':'<4>1 2026-10-06T23:02:26+02:00 home-server-mc kernel - - -  FW-SERVEUR-IN IN=ens3 OUT= MAC=x SRC=8.8.8.8 DST=192.168.4.10 LEN=60 PROTO=TCP SPT=54126 DPT=49150 SYN',
    'net_udp':'<30>1 2026-10-07T18:52:44Z home-server-services Home_server-NETFLOW 2949 - - [1791399164.486998] [NEW] ipv4 2 udp 17 30 src=127.0.0.1 dst=127.0.0.53 sport=49469 dport=53 [UNREPLIED] src=127.0.0.53 dst=127.0.0.1 sport=53 dport=49469',
    'net_tcp':'<30>1 2026-10-07T18:52:01Z home-server-services Home_server-NETFLOW 2949 - - [1791399121.720333] [UPDATE] ipv4 2 tcp 6 30 LAST_ACK src=127.0.0.1 dst=127.0.0.1 sport=60412 dport=6379 src=127.0.0.1 dst=127.0.0.1 sport=6379 dport=60412 [ASSURED]',
    'probe_drop':'<4>1 2026-10-07T18:53:09Z home-server-mc kernel - - - FW-SERVEUR-IN IN=ens3 OUT= MAC=x SRC=192.168.5.10 DST=192.168.4.10 LEN=60 PROTO=TCP SPT=45122 DPT=9940 SYN',
    'ssh':'<38>1 2026-10-06T23:05:00+02:00 home-server sshd 100 - - Accepted publickey for patrick from 10.10.10.2 port 50000 ssh2',
    'ptero':'<30>1 2026-10-07T20:53:01+02:00 home-server-services CRON 1 - - (www-data) CMD (/usr/bin/php /var/www/pterodactyl/artisan schedule:run >> /dev/null 2>&1)',
    'pam':'<30>1 2026-10-07T20:53:01+02:00 home-server-services CRON 1 - - pam_unix(cron:session): session opened for user www-data(uid=33) by www-data(uid=0)',
    'igmp':'<4>1 2026-10-07T20:53:16+02:00 home-server kernel - - - FW-HOTE-IN IN=br-mgmt OUT= MAC=x SRC=192.168.3.1 DST=224.0.0.1 LEN=28 PROTO=2',
}

# UTC RFC5424 doit être converti en Europe/Paris (CEST le 07/10/2026).
p=m.parse_raw(samples['net_udp'])
assert p['heure']=='20:52:44', p

for rel in ('config.json','identities.json','rules.json','mail-policy.json'):
    json.loads((ROOT/'etc/Home_server-events-v2'/rel).read_text())

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    cfg=json.loads((ROOT/'etc/Home_server-events-v2/config.json').read_text())
    cfg['output_log']=str(td/'v2.jsonl')
    cfg['state_file']=str(td/'state.json')
    e=m.Engine(cfg, json.loads((ROOT/'etc/Home_server-events-v2/identities.json').read_text()), {'rules':[]})

    e.process(samples['etat'])
    e.process(samples['net_udp'])
    e.process(samples['net_tcp'])
    e.process(samples['probe_drop'])
    e.process(samples['probe_drop']) # pas de seconde alerte : état déjà down
    e.process(samples['pam'])
    e.process(samples['ptero'])
    e.process(samples['igmp'])
    e.process(samples['ssh'])

    rows=[json.loads(x) for x in (td/'v2.jsonl').read_text().splitlines()]
    types=[r['type'] for r in rows]
    assert types == [
        'supervision.check.ok',
        'supervision.minecraft.down',
        'ptero.schedule',
        'firewall.denied',
        'ssh.login.known_ip',
    ], types
    assert rows[1]['source']=='vm_logs' and rows[1]['message']=='Exporteur Minecraft inaccessible sur vm_mc:9940'
    assert rows[2]['message']=='Tâche planifiée Pterodactyl exécutée'
    assert 'multicast IGMP' in rows[3]['message'] and rows[3]['protocole']=='IGMP'
    assert 'PC-Grenoble' in rows[4]['message']
    assert not any('LAST_ACK' in r['message'] or 'UNREPLIED' in r['message'] for r in rows)

print('Tests V2 v2 OK')
