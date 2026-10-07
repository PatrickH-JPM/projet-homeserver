#!/usr/bin/env python3
"""Create two Ubuntu KVM guests from official image, no private key in guests."""
import hashlib,json,os,subprocess,sys,tempfile,urllib.request
from pathlib import Path
import xml.etree.ElementTree as ET
if os.geteuid()!=0 or Path('/etc/Home_server-role').read_text().strip()!='host':raise SystemExit('Executer avec sudo sur Home_server')
key=Path(sys.argv[1]).read_text().strip() if len(sys.argv)>1 else ''
if not key.startswith('ssh-ed25519 ') or '\n' in key:raise SystemExit('Indiquer le fichier de cle publique ED25519 du PC')
cfg=json.loads(Path('/etc/Home_server-deploiement/parametres.json').read_text())
def run(*cmd):subprocess.run(cmd,check=True)
run('apt-get','install','-y','cloud-image-utils','qemu-utils','python3-yaml')
run('systemctl','start','Home_server-host-firewall')
run('virsh','-c','qemu:///system','list')
folder=Path('/var/lib/libvirt/images');folder.mkdir(exist_ok=True,parents=True)
base=folder/'Home_server-ubuntu24.img'
url='https://cloud-images.ubuntu.com/releases/noble/release/'
filename='ubuntu-24.04-server-cloudimg-amd64.img'
# SHA256SUMS via Canonical HTTPS; fail if remote image changes during download.
sums=urllib.request.urlopen(url+'SHA256SUMS',timeout=60).read().decode()
expected=[line.split()[0] for line in sums.splitlines() if line.split()[-1].lstrip('*')==filename]
if len(expected)!=1:raise SystemExit('Somme officielle introuvable')
if not base.exists():
 urllib.request.urlretrieve(url+filename,str(base)+'.part');Path(str(base)+'.part').replace(base)
if hashlib.sha256(base.read_bytes()).hexdigest()!=expected[0]:raise SystemExit('Image differente de la somme Canonical. Retirer uniquement le fichier image de base puis relancer.')
import yaml
for name,ip,bridge,ram,vcpus,mac in [('Home_server_mc','192.168.4.10','br-game',9216,4,'52:54:00:48:04:10'),('Home_server_services','192.168.5.10','br-svc',4096,2,'52:54:00:48:05:10')]:
 existing=subprocess.run(['virsh','-c','qemu:///system','dominfo',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 if existing.returncode==0:raise SystemExit(name+' existe deja; aucune suppression automatique')
 disk=folder/(name+'.qcow2')
 if disk.exists():raise SystemExit('Disque existant '+str(disk))
 run('qemu-img','convert','-O','qcow2',str(base),str(disk));run('qemu-img','resize',str(disk),'60G')
 data={'hostname':name.lower().replace('_','-'),'users':[{'name':'patrick','groups':['sudo','adm'],'shell':'/bin/bash','sudo':['ALL=(ALL) NOPASSWD:ALL'],'lock_passwd':True,'ssh_authorized_keys':[key]}],'ssh_pwauth':False,'disable_root':True,'package_update':True,'packages':['openssh-server','git','python3'],'write_files':[{'path':'/etc/sysctl.d/90-Home_server-ipv6.conf','content':'net.ipv6.conf.all.disable_ipv6=1\nnet.ipv6.conf.default.disable_ipv6=1\n'}],'runcmd':[['sysctl','--system']]}
 network={'version':2,'ethernets':{'main':{'match':{'macaddress':mac},'set-name':'ens3','addresses':[ip+'/24'],'routes':[{'to':'default','via':ip.rsplit('.',1)[0]+'.1'}],'nameservers':{'addresses':cfg['dns_ips']},'dhcp6':False,'accept-ra':False}}}
 with tempfile.TemporaryDirectory(prefix='Home_server-') as td:
  user=Path(td)/'user.yaml';user.write_text('#cloud-config\n'+yaml.safe_dump(data));net=Path(td)/'net.yaml';net.write_text(yaml.safe_dump(network));meta=Path(td)/'meta.yaml';meta.write_text('instance-id: '+name+'\n')
  seed=folder/(name+'-seed.iso');run('cloud-localds','--network-config='+str(net),str(seed),str(user),str(meta))
  command=['virt-install','--connect','qemu:///system','--name',name,'--memory',str(ram),'--vcpus',str(vcpus),'--cpu','host-passthrough','--import','--osinfo','ubuntu24.04','--disk','path='+str(disk)+',bus=virtio','--disk','path='+str(seed)+',device=cdrom','--network','bridge='+bridge+',model=virtio,mac='+mac,'--graphics','none','--noautoconsole','--print-xml']
  xml=subprocess.check_output(command,text=True)
  root=ET.fromstring(xml)
  interface=root.find('devices/interface')
  if interface is None:raise SystemExit('Interface XML manquante')
  filterref=ET.SubElement(interface,'filterref',{'filter':'clean-traffic'})
  ET.SubElement(filterref,'parameter',{'name':'IP','value':ip})
  domain=Path(td)/'domain.xml';domain.write_text(ET.tostring(root,encoding='unicode'))
  run('virsh','-c','qemu:///system','define',str(domain))
  run('virsh','-c','qemu:///system','start',name)
 run('virsh','-c','qemu:///system','autostart',name)
 print(name+' cree. SSH: patrick@'+ip+'; cle du PC uniquement.')
