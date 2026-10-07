#!/usr/bin/env python3
import os,subprocess
from pathlib import Path
import yaml
if os.geteuid()!=0 or Path('/etc/Home_server-role').read_text().strip()!='game':raise SystemExit('Executer avec sudo sur Home_server_mc')
p=Path('/etc/pterodactyl/config.yml')
c=yaml.safe_load(p.read_text())
if not isinstance(c,dict) or not all(c.get(k) for k in ('uuid','token','token_id')):raise SystemExit('Copier auparavant la configuration complete fournie par le Panel')
Path(str(p)+'.original').write_text(p.read_text());Path(str(p)+'.original').chmod(0o600)
a=c.setdefault('api',{});a['host']='192.168.4.10';a['port']=8080;a['ssl']={'enabled':True,'cert':'/etc/Home_server-pki/wings.crt','key':'/etc/Home_server-pki/wings.key'};a['trusted_proxies']=['192.168.5.10']
c['remote']='https://panel.home.arpa'
d=c.setdefault('docker',{});n=d.setdefault('network',{});n['name']='pterodactyl_nw';n['interface']='172.18.0.1';n['is_internal']=False;n['driver']='bridge';n.setdefault('interfaces',{})['v4']={'subnet':'172.18.0.0/16','gateway':'172.18.0.1'}
n['dns']=['9.9.9.9','149.112.112.112']
c.setdefault('system',{}).setdefault('sftp',{})['bind_address']='192.168.4.10';c['system']['sftp']['bind_port']=2022
p.write_text(yaml.safe_dump(c,sort_keys=False));p.chmod(0o600)
print('Configuration Wings ajustee. Tokens conserves, TLS active.')
