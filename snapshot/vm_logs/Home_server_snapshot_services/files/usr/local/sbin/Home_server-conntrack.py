#!/usr/bin/python3
"""Snapshot conntrack -> Prometheus textfile.

V4.1:
- conserve l'historique par etat TCP/UDP;
- distingue les connexions WAN ENTRANTES (IP publique -> IP locale);
- expose IP distante, protocole, port/service et nombre de connexions actives;
- expose les pairs WireGuard 10.10.10.x vus actifs avec un nom lisible.

Le journal conntrack -E reste inchangé et exhaustif.
"""
import ipaddress
import json
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path

OUT = Path('/var/lib/Home_server-textfile/conntrack.prom')
PEERS_CFG = Path('/etc/Home_server-wireguard-peers.json')
TCP_STATES = ('ESTABLISHED','SYN_SENT','SYN_RECV','TIME_WAIT','FIN_WAIT','CLOSE_WAIT','CLOSE','LAST_ACK')
WG_NET = ipaddress.ip_network('10.10.10.0/24')
DEFAULT_WG_NAMES = {'10.10.10.2': 'PC Patrick'}
SERVICE_NAMES = {
    ('tcp', 22): 'SSH',
    ('tcp', 80): 'HTTP',
    ('tcp', 443): 'HTTPS',
    ('tcp', 49150): 'Minecraft',
    ('udp', 51820): 'WireGuard',
}


def q(value):
    return json.dumps(str(value), ensure_ascii=True)


def atomic(text):
    tmp = OUT.with_name(OUT.name + '.tmp')
    tmp.write_text(text, encoding='ascii')
    os.chmod(tmp, 0o644)
    os.replace(tmp, OUT)


def load_wg_names():
    names = dict(DEFAULT_WG_NAMES)
    try:
        data = json.loads(PEERS_CFG.read_text())
        if isinstance(data, dict):
            for ip, name in data.items():
                if isinstance(ip, str) and isinstance(name, str) and name.strip():
                    names[ip] = name.strip()
    except (OSError, ValueError):
        pass
    return names


def first_tuple(line):
    """Retourne le tuple original conntrack (avant le tuple reply)."""
    src = re.search(r'\bsrc=([0-9.]+)', line)
    dst = re.search(r'\bdst=([0-9.]+)', line)
    sport = re.search(r'\bsport=(\d+)', line)
    dport = re.search(r'\bdport=(\d+)', line)
    if not src or not dst:
        return None
    return src.group(1), dst.group(1), int(sport.group(1)) if sport else 0, int(dport.group(1)) if dport else 0


def is_local_v4(raw):
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return False
    return ip.version == 4 and not ip.is_global


def is_global_v4(raw):
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return False
    return ip.version == 4 and ip.is_global


def main():
    now = time.time()
    rows = [f'Home_server_conntrack_collecte_timestamp_seconds {now}']
    states = Counter({s: 0 for s in TCP_STATES})
    states['UDP'] = 0
    wan_inbound = Counter()
    wireguard = Counter()
    wg_names = load_wg_names()

    try:
        p = subprocess.run(['conntrack','-L','-o','extended'], text=True,
                           capture_output=True, timeout=10)
        if p.returncode not in (0, 1):
            raise RuntimeError(p.stderr.strip()[:300])
        lines = p.stdout.splitlines()
        rows.append('Home_server_conntrack_collector_up 1')
        rows.append(f'Home_server_conntrack_entries_total {len(lines)}')

        for line in lines:
            words = line.split()
            proto = next((w.lower() for w in words[:3] if w.lower() in ('tcp','udp')), '')
            state = next((s for s in TCP_STATES if re.search(r'\b' + s + r'\b', line)), None)
            if proto == 'udp':
                states['UDP'] += 1
            elif state:
                states[state] += 1

            tup = first_tuple(line)
            if not tup:
                continue
            src, dst, sport, dport = tup
            active = (proto == 'tcp' and state == 'ESTABLISHED') or (proto == 'udp' and '[ASSURED]' in line)

            # WireGuard: pair 10.10.10.x implique dans une entree conntrack active.
            if active:
                for raw in (src, dst):
                    try:
                        ip = ipaddress.ip_address(raw)
                    except ValueError:
                        continue
                    if ip.version == 4 and ip in WG_NET and raw != '10.10.10.1':
                        wireguard[raw] += 1

            # WAN entrant uniquement : tuple original IP publique -> adresse locale.
            # Les connexions sortantes (local -> Internet) ne sont donc jamais listees ici.
            if active and is_global_v4(src) and is_local_v4(dst):
                service = SERVICE_NAMES.get((proto, dport), str(dport) if dport else 'inconnu')
                wan_inbound[(src, proto or 'autre', dport, service)] += 1

        for state_name in list(TCP_STATES) + ['UDP']:
            rows.append(f'Home_server_conntrack_connections{{state={q(state_name)}}} {states[state_name]}')

        total_conn = sum(wan_inbound.values())
        unique_peers = len({k[0] for k in wan_inbound})
        rows.append(f'Home_server_wan_inbound_connections_total {total_conn}')
        rows.append(f'Home_server_wan_inbound_peers_total {unique_peers}')
        for (peer, proto, port, service), count in wan_inbound.most_common(200):
            labels = f'peer={q(peer)},protocol={q(proto)},port={q(port)},service={q(service)}'
            rows.append(f'Home_server_wan_inbound_connections{{{labels}}} {count}')

        for peer, count in wireguard.most_common(64):
            name = wg_names.get(peer, 'Inconnu')
            rows.append(f'Home_server_wireguard_peer_active{{peer={q(peer)},name={q(name)}}} 1')
            rows.append(f'Home_server_wireguard_peer_connections{{peer={q(peer)},name={q(name)}}} {count}')

    except Exception as exc:
        rows.append('Home_server_conntrack_collector_up 0')
        subprocess.run(['logger','-p','user.warning','-t','Home_server-CONNTRACK',
                        'Snapshot conntrack impossible: ' + str(exc)[:300]], check=False)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic('\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()
