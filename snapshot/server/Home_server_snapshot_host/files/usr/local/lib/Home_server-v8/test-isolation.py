#!/usr/bin/env python3
"""Few controlled frames to the administrator PC; no scan, no configuration change."""
import json,os,re
from pathlib import Path
from scapy.all import ARP,Dot1Q,Ether,IP,TCP,get_if_hwaddr,sendp,srp
if os.geteuid()!=0 or Path('/etc/Home_server-role').read_text().strip()!='host':raise SystemExit('Executer avec sudo sur Home_server')
cfg=json.loads(Path('/etc/Home_server-deploiement/parametres.json').read_text())
nic=cfg['nic'];pc=cfg['pc_ip'];mac=get_if_hwaddr(nic)
print('Quelques SYN uniquement vers le PC',pc,'port8765. Observer Wireshark sur ce PC.')
for vlan,source,gateway in [(3,'192.168.3.10','192.168.3.1'),(4,'192.168.4.10','192.168.4.1'),(5,'192.168.5.10','192.168.5.1')]:
 ether=Ether(src=mac,dst='ff:ff:ff:ff:ff:ff')
 layer=Dot1Q(vlan=vlan) if vlan!=3 else None
 request=ether/layer/ARP(op=1,psrc=source,pdst=gateway,hwsrc=mac) if layer else ether/ARP(op=1,psrc=source,pdst=gateway,hwsrc=mac)
 replies,_=srp(request,iface=nic,timeout=3,verbose=False)
 if not replies:raise SystemExit('Passerelle VLAN'+str(vlan)+' sans reponse ARP. Le test est incomplet.')
 gm=replies[0][1][ARP].hwsrc
 for spoof in (source,'10.10.10.2','10.10.10.4'):
  base=Ether(src=mac,dst=gm)
  if layer:base=base/Dot1Q(vlan=vlan)
  sendp(base/IP(src=spoof,dst=pc)/TCP(sport=48000+vlan,dport=8765,flags='S'),iface=nic,count=1,verbose=False)
  print('Envoye VLAN',vlan,'source',spoof)
# VLAN2 must not be a member of the server port. Broadcast destination also reaches a wrongly admitted VLAN.
sendp(Ether(src=mac,dst='ff:ff:ff:ff:ff:ff')/Dot1Q(vlan=2)/IP(src='192.168.2.99',dst=pc)/TCP(sport=48002,dport=8765,flags='S'),iface=nic,count=1,verbose=False)
print('Termine. Resultat valide seulement si aucun de ces SYN ne parvient au PC. Verifier que la capture fonctionnait avec un controle positif.')
