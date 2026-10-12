#!/usr/bin/python3
"""Snapshot conntrack -> Prometheus textfile.

Le journal conntrack -E reste inchangé et exhaustif. Ce collecteur ajoute seulement
un état courant agrégé pour les graphes Grafana ; il ne filtre ni ne supprime aucun log.
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
TCP_STATES = ('ESTABLISHED','SYN_SENT','SYN_RECV','TIME_WAIT','FIN_WAIT','CLOSE_WAIT','CLOSE','LAST_ACK')
WG_NET = ipaddress.ip_network('10.10.10.0/24')


def q(value):
    return json.dumps(str(value), ensure_ascii=True)


def atomic(text):
    tmp = OUT.with_name(OUT.name + '.tmp')
    tmp.write_text(text, encoding='ascii')
    os.chmod(tmp, 0o644)
    os.replace(tmp, OUT)


def main():
    now = time.time()
    rows = [f'Home_server_conntrack_collecte_timestamp_seconds {now}']
    states = Counter({s: 0 for s in TCP_STATES})
    states['UDP'] = 0
    external = Counter()
    wireguard = Counter()
    truncated = 0

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

            m = re.search(r'\bsrc=([0-9.]+)\s+dst=([0-9.]+)', line)
            if not m:
                continue
            src, dst = m.group(1), m.group(2)
            active = (proto == 'tcp' and state == 'ESTABLISHED') or (proto == 'udp' and '[ASSURED]' in line)
            for raw in (src, dst):
                try:
                    ip = ipaddress.ip_address(raw)
                except ValueError:
                    continue
                if ip.version != 4:
                    continue
                if ip in WG_NET and raw != '10.10.10.1':
                    wireguard[raw] += 1
                if active and ip.is_global:
                    external[raw] += 1

        for state in list(TCP_STATES) + ['UDP']:
            rows.append(f'Home_server_conntrack_connections{{state={q(state)}}} {states[state]}')

        # Les IPs sont limitées aux connexions réellement établies/assurées, pas aux SYN/scans.
        for peer, count in external.most_common(200):
            rows.append(f'Home_server_external_peer_present{{peer={q(peer)}}} 1')
            rows.append(f'Home_server_external_peer_connections{{peer={q(peer)}}} {count}')
        if len(external) > 200:
            truncated = 1
        rows.append(f'Home_server_external_peer_truncated {truncated}')

        for peer, count in wireguard.most_common(64):
            rows.append(f'Home_server_wireguard_peer_present{{peer={q(peer)}}} 1')
            rows.append(f'Home_server_wireguard_peer_connections{{peer={q(peer)}}} {count}')

    except Exception as exc:
        rows.append('Home_server_conntrack_collector_up 0')
        subprocess.run(['logger','-p','user.warning','-t','Home_server-CONNTRACK',
                        'Snapshot conntrack impossible: ' + str(exc)[:300]], check=False)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic('\n'.join(rows) + '\n')


if __name__ == '__main__':
    main()
