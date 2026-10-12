#!/usr/bin/python3
import json, os, subprocess, time
from pathlib import Path
from datetime import datetime,timezone
OUT = '/var/lib/Home_server-textfile/docker.prom'

def run(*args):
    return subprocess.run(args, check=True, text=True,
                          capture_output=True, timeout=10).stdout

def quoted(value):
    return json.dumps(str(value), ensure_ascii=True)

role = open('/etc/Home_server-role').read().strip()
rows = ['Home_server_collecte_timestamp_seconds %s' % time.time()]
previous_path=Path('/var/lib/Home_server-textfile/etat.json')
try: previous=json.loads(previous_path.read_text())
except (OSError,ValueError): previous={}
current={}
try:
    ids = run('docker', 'ps', '-aq').split() if role != 'host' else []
    for ident in ids:
        obj = json.loads(run('docker', 'inspect', ident))[0]
        name = obj['Name'].lstrip('/')
        label = '{container=%s}' % quoted(name)
        state = obj['State']
        current[name]=bool(state['Running'])
        if name in previous and previous[name] != current[name]:
            subprocess.run(['logger','-t','Home_server-DOCKER','SECURITY etat conteneur '+name+' running='+str(current[name])+' exit='+str(state.get('ExitCode'))+' OOM='+str(state.get('OOMKilled'))],check=False)
        rows.append('Home_server_container_running%s %d' %
                    (label, int(state['Running'])))
        rows.append('Home_server_container_restart_total%s %d' %
                    (label, obj.get('RestartCount', 0)))
        rows.append('Home_server_container_oom%s %d' %
                    (label, int(state.get('OOMKilled', False))))
    if role != 'host':
        rows.append('Home_server_docker_collecte_ok 1')
except (OSError, subprocess.SubprocessError, ValueError, KeyError):
    rows.append('Home_server_docker_collecte_ok 0')
role = open('/etc/Home_server-role').read().strip()
services = ('ssh', 'rsyslog')
if role != 'host':
    services += ('crowdsec', 'crowdsec-firewall-bouncer')
    services += ('wings',) if role == 'game' else ('nginx', 'pteroq')
for service in services:
    result = subprocess.run(['systemctl', 'is-active', service],
                            capture_output=True, text=True, timeout=5)
    rows.append('Home_server_service_active{service=%s} %d' %
                (quoted(service), int(result.stdout.strip() == 'active')))
temp = OUT + '.tmp'
with open(temp, 'w', encoding='ascii') as f:
    f.write('\n'.join(rows) + '\n')
os.chmod(temp, 0o644)
os.replace(temp, OUT)

for cert in Path('/etc/Home_server-pki').glob('*.crt'):
    result=subprocess.run(['openssl','x509','-enddate','-noout','-in',str(cert)],capture_output=True,text=True,timeout=5)
    if result.returncode==0:
        expiry=datetime.strptime(result.stdout.strip().split('=',1)[1],'%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc).timestamp()
        marker=Path('/var/lib/Home_server-textfile/tls-'+cert.name+'.alerte')
        due=(not marker.exists()) or time.time()-marker.stat().st_mtime>86400
        if expiry-time.time()<30*86400 and due:
            marker.write_text('alerte')
            subprocess.run(['logger','-p','user.err','-t','Home_server-TLS','SECURITY certificat expire dans moins de 30 jours '+cert.name],check=False)
previous_path.write_text(json.dumps(current))
previous_path.chmod(0o600)
