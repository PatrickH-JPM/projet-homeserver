#!/usr/bin/python3
"""Normaliseur d'événements Home_server V2.

Lit directement /var/log/Home_server/brut.log. Aucune dépendance à evenements.jsonl.
Le journal brut reste la référence technique complète ; ce programme produit une vue
humaine structurée et destinée au terminal/Grafana/filtre mail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import sys
import time
from datetime import datetime
from typing import Any

CFG_DIR = Path('/etc/Home_server-events-v2')
CONFIG_PATH = CFG_DIR / 'config.json'
IDENTITIES_PATH = CFG_DIR / 'identities.json'
RULES_PATH = CFG_DIR / 'rules.json'

MONTHS = {m: i for i, m in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'), 1)}

RFC5424 = re.compile(
    r'^<(?P<pri>\d+)>1\s+(?P<dt>\S+)\s+(?P<host>\S+)\s+(?P<program>\S+)\s+' 
    r'(?P<pid>\S+)\s+(?P<msgid>\S+)\s+-\s*(?P<msg>.*)$'
)
RFC3164 = re.compile(
    r'^<(?P<pri>\d+)>(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+' 
    r'(?P<hms>\d{2}:\d{2}:\d{2})\s+(?P<head>[^:]+):\s*(?P<msg>.*)$'
)
FIREWALL = re.compile(
    r'(?P<prefix>FW-(?:SERVEUR|DOCKER|HOTE)(?:-(?:IN|OUT))?)\b.*?'
    r'\bSRC=(?P<src>[0-9.]+)\s+DST=(?P<dst>[0-9.]+).*?'
    r'\bPROTO=(?P<proto>[A-Z0-9]+)'
    r'(?:\s+SPT=(?P<sport>\d+)\s+DPT=(?P<dport>\d+))?', re.I
)
CONNTRACK = re.compile(
    r'\[(?P<action>NEW|UPDATE|DESTROY)\].*?\b(?P<state>SYN_SENT|SYN_RECV|ESTABLISHED|FIN_WAIT|CLOSE_WAIT|CLOSE|TIME_WAIT)\b.*?'
    r'\bsrc=(?P<src>[0-9.]+)\s+dst=(?P<dst>[0-9.]+)\s+sport=(?P<sport>\d+)\s+dport=(?P<dport>\d+)', re.I
)
SSH_OK = re.compile(r'Accepted\s+\S+\s+for\s+(?P<user>\S+)\s+from\s+(?P<ip>[0-9a-fA-F:.]+)\s+port\s+(?P<port>\d+)', re.I)
SSH_FAIL = re.compile(r'Failed\s+\S+\s+for(?: invalid user)?\s+(?P<user>\S+)\s+from\s+(?P<ip>[0-9a-fA-F:.]+)\s+port\s+(?P<port>\d+)', re.I)
MC_LOGIN = re.compile(r'(?P<player>[A-Za-z0-9_]{1,32}).*?logged in with entity.*?/(?P<ip>[0-9.]+):(?P<port>\d+)', re.I)
MC_JOIN = re.compile(r'(?P<player>[A-Za-z0-9_]{1,32}) joined the game', re.I)
MC_LEAVE = re.compile(r'(?P<player>[A-Za-z0-9_]{1,32}) left the game', re.I)
IP_RE = re.compile(r'(?<![0-9])(?:\d{1,3}\.){3}\d{1,3}(?![0-9])')

RUNNING = True

def stop_handler(_signum, _frame):
    global RUNNING
    RUNNING = False

signal.signal(signal.SIGTERM, stop_handler)
signal.signal(signal.SIGINT, stop_handler)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def atomic_json(path: Path, obj: Any, mode: int = 0o640) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def now_parts() -> tuple[str, str]:
    d = datetime.now().astimezone()
    return d.strftime('%d/%m/%Y'), d.strftime('%H:%M:%S')


def iso_parts(value: str) -> tuple[str, str]:
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        # Après réglage des 3 Linux en Europe/Paris, les nouveaux logs portent déjà
        # l'heure locale correcte. On conserve donc l'heure exprimée par la source.
        return d.strftime('%d/%m/%Y'), d.strftime('%H:%M:%S')
    except ValueError:
        return now_parts()


def parse_raw(line: str) -> dict[str, Any]:
    line = line.rstrip('\n')
    m = RFC5424.match(line)
    if m:
        pri = int(m['pri'])
        date, heure = iso_parts(m['dt'])
        return {
            'date': date, 'heure': heure, 'pri': pri, 'severity': pri % 8,
            'host': m['host'], 'program': m['program'], 'message': m['msg'], 'raw': line
        }

    m = RFC3164.match(line)
    if m:
        pri = int(m['pri'])
        head = m['head'].strip()
        program = re.sub(r'\[\d+\]$', '', head)
        host = 'home-server-services'
        # ER605 écrit son nom à la place du programme dans ses trames RFC3164.
        if head.upper() == 'ER605':
            host = 'ER605'
            program = 'ER605'
        date = f"{int(m['day']):02d}/{MONTHS.get(m['mon'], datetime.now().month):02d}/{datetime.now().year}"
        return {
            'date': date, 'heure': m['hms'], 'pri': pri, 'severity': pri % 8,
            'host': host, 'program': program, 'message': m['msg'], 'raw': line
        }

    # Fallback pour quelques lignes kernel brutes sans en-tête syslog complet.
    date, heure = now_parts()
    source = 'home-server-services'
    if 'FW-HOTE' in line:
        source = 'home-server'
    elif 'FW-SERVEUR' in line or 'FW-DOCKER' in line:
        dst = re.search(r'\bDST=([0-9.]+)', line)
        src = re.search(r'\bSRC=([0-9.]+)', line)
        ip = (dst or src).group(1) if (dst or src) else ''
        if ip == '192.168.4.10':
            source = 'home-server-mc'
        elif ip == '192.168.5.10':
            source = 'home-server-services'
    return {
        'date': date, 'heure': heure, 'pri': None, 'severity': 6,
        'host': source, 'program': '', 'message': line.strip(), 'raw': line
    }


class Engine:
    def __init__(self, cfg: dict[str, Any], identities: dict[str, Any], rules: dict[str, Any]):
        self.cfg = cfg
        self.identities = identities
        self.rules = [(r, re.compile(r['regex'], re.I)) for r in rules.get('rules', [])]
        self.output = Path(cfg['output_log'])
        self.state_path = Path(cfg['state_file'])
        self.state = load_json(self.state_path, {})
        self.state.setdefault('known_authenticated_ips', {})
        self.state.setdefault('firewall', {})
        self.state.setdefault('scan', {})
        self.state.setdefault('ssh_fail', {})
        self.state.setdefault('probes', {})
        self.state.setdefault('heartbeats', {})
        self.state.setdefault('input_cursor', {})
        self.pending_probes: dict[str, dict[str, Any]] = {}
        self.dirty = False
        self.last_state_write = 0.0

    def source_alias(self, host: str) -> str:
        return self.cfg.get('sources', {}).get(host, host or 'vm_logs')

    def ip_name(self, ip: str) -> str:
        item = self.identities.get(ip)
        if isinstance(item, dict) and item.get('name'):
            return str(item['name'])
        return self.cfg.get('known_addresses', {}).get(ip, ip)

    def mark_authenticated(self, ip: str, service: str) -> tuple[bool, str]:
        known = self.state['known_authenticated_ips']
        preconfigured = ip in self.identities
        was_known = preconfigured or ip in known
        item = known.setdefault(ip, {'services': [], 'count': 0})
        if service not in item['services']:
            item['services'].append(service)
        item['count'] = int(item.get('count', 0)) + 1
        self.dirty = True
        return (not was_known), self.ip_name(ip)

    def emit(self, source: str, category: str, level: str, event_type: str,
             message: str, parsed: dict[str, Any] | None = None, **details: Any) -> None:
        date, heure = (parsed['date'], parsed['heure']) if parsed else now_parts()
        clean = {k: v for k, v in details.items() if v not in (None, '', [])}
        event_key = clean.pop('event_key', None)
        if not event_key:
            seed = '|'.join([source, category, event_type, message])
            event_key = hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]
        obj = {
            'date': date,
            'heure': heure,
            'source': source,
            'categorie': category,
            'niveau': level,
            'type': event_type,
            'message': message,
            'event_key': event_key,
            **clean,
        }
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with self.output.open('a', encoding='utf-8') as f:
            f.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n')

    def probe_match(self, source: str, src: str, dst: str, dport: int) -> dict[str, Any] | None:
        for p in self.cfg.get('service_probes', []):
            if p.get('source') != source:
                continue
            if p.get('src_ip') == src and p.get('dst_ip') == dst and int(p.get('dst_port')) == dport:
                return p
        return None

    def handle_conntrack(self, p: dict[str, Any], source: str) -> bool:
        m = CONNTRACK.search(p['message'])
        if not m:
            return False
        src, dst = m['src'], m['dst']
        sport, dport = int(m['sport']), int(m['dport'])
        state = m['state'].upper()
        probe = self.probe_match(source, src, dst, dport)

        # Les cycles TCP complets ne sont jamais envoyés vers le journal humain.
        # Seuls les changements d'état d'un service connu sont émis.
        if probe:
            pid = probe['id']
            if state == 'SYN_SENT':
                self.pending_probes.setdefault(pid, {
                    'deadline': time.monotonic() + float(self.cfg.get('probe_timeout_seconds', 5)),
                    'probe': probe,
                    'parsed': p,
                })
            elif state == 'ESTABLISHED':
                self.pending_probes.pop(pid, None)
                previous = self.state['probes'].get(pid)
                self.state['probes'][pid] = 'up'
                self.dirty = True
                if previous != 'up':
                    self.emit(source, probe['category'], probe['up_level'], probe['up_type'],
                              probe['up_message'], p, service=probe.get('service'),
                              src_ip=src, dst_ip=dst, src_port=sport, dst_port=dport,
                              protocole='TCP', event_key='probe:' + pid)
            return True

        # Pour tous les autres flux conntrack : pas de pollution du journal V2.
        # Le détail complet reste disponible dans brut.log.
        return True

    def expire_probes(self) -> None:
        now = time.monotonic()
        for pid, item in list(self.pending_probes.items()):
            if now < item['deadline']:
                continue
            probe = item['probe']
            previous = self.state['probes'].get(pid)
            self.state['probes'][pid] = 'down'
            self.dirty = True
            if previous != 'down':
                self.emit(probe['source'], probe['category'], probe['down_level'], probe['down_type'],
                          probe['down_message'], item['parsed'], service=probe.get('service'),
                          src_ip=probe.get('src_ip'), dst_ip=probe.get('dst_ip'),
                          dst_port=probe.get('dst_port'), protocole='TCP', event_key='probe:' + pid)
            self.pending_probes.pop(pid, None)

    def handle_firewall(self, p: dict[str, Any], source: str) -> bool:
        m = FIREWALL.search(p['message'])
        if not m:
            return False
        src, dst = m['src'], m['dst']
        proto = m['proto'].upper()
        sport = int(m['sport']) if m['sport'] else None
        dport = int(m['dport']) if m['dport'] else None
        now = time.monotonic()
        window = float(self.cfg.get('firewall_counter_window_seconds', 60))
        key = f"{source}|{src}|{dst}|{proto}|{dport or 0}"
        fw = self.state['firewall'].get(key)
        if not fw or now - float(fw.get('_mono', 0)) > window:
            fw = {'count': 0, '_mono': now}
        fw['count'] = int(fw.get('count', 0)) + 1
        fw['_mono'] = now
        self.state['firewall'][key] = fw
        self.dirty = True
        count = fw['count']
        level = 'INFO' if count == 1 else 'ALERTE'
        src_name, dst_name = self.ip_name(src), self.ip_name(dst)
        target = f"{dst_name} ({dst})"
        if dport:
            target += f":{dport}/{proto}"
        else:
            target += f"/{proto}"
        msg = f"Connexion refusée : {src_name} ({src}) → {target}"
        if count > 1:
            msg += f" — x{count} en {int(window)} s"
        self.emit(source, 'PARE-FEU', level, 'firewall.denied', msg, p,
                  src_ip=src, dst_ip=dst, src_port=sport, dst_port=dport,
                  protocole=proto, count=count, event_key='fw:' + hashlib.sha1(key.encode()).hexdigest()[:12])
        self.track_scan(p, source, src, dport)
        return True

    def track_scan(self, p: dict[str, Any], source: str, src: str, dport: int | None) -> None:
        if dport is None or src.startswith(('127.', '192.168.', '10.')):
            return
        now = time.monotonic()
        window = float(self.cfg.get('scan_window_seconds', 60))
        threshold = int(self.cfg.get('scan_distinct_ports_threshold', 20))
        item = self.state['scan'].get(src)
        if not item or now - float(item.get('_mono', 0)) > window:
            item = {'ports': [], '_mono': now, 'alerted': False}
        ports = set(int(x) for x in item.get('ports', []))
        ports.add(dport)
        item['ports'] = sorted(ports)
        item['_mono'] = now
        if len(ports) >= threshold and not item.get('alerted'):
            item['alerted'] = True
            self.emit(source, 'PARE-FEU', 'ALERTE', 'security.scan',
                      f"Scan de ports suspecté depuis {src} : {len(ports)} ports distincts en {int(window)} s",
                      p, src_ip=src, count=len(ports), event_key='scan:' + src)
        self.state['scan'][src] = item
        self.dirty = True

    def handle_etat_service(self, p: dict[str, Any], source: str) -> bool:
        msg = p['message']
        if 'Starting Home_server-etat.service' in msg or 'Home_server-etat.service: Deactivated successfully' in msg:
            return True
        if 'Finished Home_server-etat.service' in msg:
            # Ne pas transformer un timer très fréquent en pollution visuelle.
            # Un heartbeat INFO est émis au plus une fois par intervalle et les
            # incidents restent, eux, émis immédiatement par leurs règles dédiées.
            interval = float(self.cfg.get('supervision_heartbeat_seconds', 60))
            now = time.monotonic()
            last = float(self.state['heartbeats'].get(source, 0) or 0)
            if last == 0 or now - last >= interval:
                human = 'Mesures locales relevées' if source == 'server' else 'État relevé : services et conteneurs OK'
                self.emit(source, 'SUPERVISION', 'INFO', 'supervision.check.ok', human, p,
                          service='Home_server-etat', event_key='etat:' + source)
                self.state['heartbeats'][source] = now
                self.dirty = True
            return True
        return False

    def handle_ssh(self, p: dict[str, Any], source: str) -> bool:
        msg = p['message']
        m = SSH_OK.search(msg)
        if m:
            ip, user = m['ip'], m['user']
            first, name = self.mark_authenticated(ip, 'ssh')
            level = 'ALERTE' if first else 'INFO'
            typ = 'ssh.login.new_ip' if first else 'ssh.login.known_ip'
            prefix = 'Première connexion SSH réussie' if first else 'Connexion SSH réussie'
            self.emit(source, 'SSH', level, typ,
                      f"{prefix} : {name} ({ip}) → utilisateur {user}", p,
                      src_ip=ip, user=user, event_key=f"ssh-ok:{ip}:{user}")
            return True
        m = SSH_FAIL.search(msg)
        if m:
            ip, user = m['ip'], m['user']
            now = time.monotonic()
            window = float(self.cfg.get('ssh_bruteforce_window_seconds', 60))
            threshold = int(self.cfg.get('ssh_bruteforce_threshold', 3))
            item = self.state['ssh_fail'].get(ip)
            if not item or now - float(item.get('_mono', 0)) > window:
                item = {'count': 0, '_mono': now, 'alerted': False}
            item['count'] += 1
            item['_mono'] = now
            count = item['count']
            self.state['ssh_fail'][ip] = item
            self.dirty = True
            if count >= threshold and not item.get('alerted'):
                item['alerted'] = True
                self.emit(source, 'SSH', 'ALERTE', 'ssh.bruteforce',
                          f"Rafale d'échecs SSH depuis {ip} : {count} tentatives en {int(window)} s",
                          p, src_ip=ip, user=user, count=count, event_key='ssh-fail:' + ip)
            else:
                self.emit(source, 'SSH', 'INFO', 'ssh.auth_failed',
                          f"Échec SSH depuis {ip} vers utilisateur {user} — x{count}", p,
                          src_ip=ip, user=user, count=count, event_key='ssh-fail:' + ip)
            return True
        return False

    def handle_minecraft(self, p: dict[str, Any], source: str) -> bool:
        msg = p['message']
        m = MC_LOGIN.search(msg)
        if m:
            ip, player = m['ip'], m['player']
            first, name = self.mark_authenticated(ip, 'minecraft')
            typ = 'minecraft.login.new_ip' if first else 'minecraft.login.known_ip'
            level = 'ALERTE' if first else 'INFO'
            prefix = 'Première connexion Minecraft depuis une IP inconnue' if first else 'Connexion Minecraft depuis IP connue'
            self.emit(source, 'MINECRAFT', level, typ,
                      f"{prefix} : {player} depuis {name} ({ip})", p,
                      src_ip=ip, player=player, event_key=f"mc-login:{ip}:{player}")
            return True
        m = MC_JOIN.search(msg)
        if m:
            self.emit(source, 'MINECRAFT', 'INFO', 'minecraft.player.join',
                      f"Joueur connecté : {m['player']}", p, player=m['player'], event_key='mc-join:' + m['player'])
            return True
        m = MC_LEAVE.search(msg)
        if m:
            self.emit(source, 'MINECRAFT', 'INFO', 'minecraft.player.leave',
                      f"Joueur déconnecté : {m['player']}", p, player=m['player'], event_key='mc-leave:' + m['player'])
            return True
        if re.search(r'Done \([0-9.]+s\)!', msg):
            self.emit(source, 'MINECRAFT', 'INFO', 'minecraft.ready', 'Serveur Minecraft prêt', p, event_key='mc-ready')
            return True
        if re.search(r'Stopping server|Stopping the server', msg, re.I):
            self.emit(source, 'MINECRAFT', 'INFO', 'minecraft.stop', 'Arrêt du serveur Minecraft demandé', p, event_key='mc-stop')
            return True
        if re.search(r'\bERROR\b|Exception|crash|OutOfMemory|OOM', msg, re.I):
            self.emit(source, 'MINECRAFT', 'ALERTE', 'minecraft.error',
                      'Erreur Minecraft : ' + msg[:450], p, event_key='mc-error:' + hashlib.sha1(msg.encode()).hexdigest()[:10])
            return True
        return False

    def handle_crowdsec(self, p: dict[str, Any], source: str) -> bool:
        program, msg = p['program'].lower(), p['message']
        if 'crowdsec' not in program and 'crowdsec' not in msg.lower():
            return False
        ip = next(iter(IP_RE.findall(msg)), None)
        if re.search(r'\bban(?:ned|ning)?\b|blocked|remediation.*ban', msg, re.I):
            text = f"IP {ip} bannie et bloquée par CrowdSec" if ip else 'Bannissement / blocage appliqué par CrowdSec'
            self.emit(source, 'CrowdSec', 'CRITIQUE', 'crowdsec.ban', text, p,
                      src_ip=ip, service='crowdsec', event_key='crowdsec-ban:' + (ip or hashlib.sha1(msg.encode()).hexdigest()[:8]))
            return True
        if re.search(r'decision|alert', msg, re.I):
            text = ('Décision CrowdSec pour ' + ip) if ip else ('Décision CrowdSec : ' + msg[:350])
            self.emit(source, 'CrowdSec', 'ALERTE', 'crowdsec.decision', text, p,
                      src_ip=ip, service='crowdsec', event_key='crowdsec-decision:' + (ip or hashlib.sha1(msg.encode()).hexdigest()[:8]))
            return True
        # Les messages purement internes CrowdSec restent disponibles dans brut.log.
        return True

    def handle_docker(self, p: dict[str, Any], source: str) -> bool:
        msg = p['message']
        if 'SECURITY etat conteneur ' in msg:
            m = re.search(r'SECURITY etat conteneur\s+(\S+)\s+running=(\S+)\s+exit=(\S+)\s+OOM=(\S+)', msg)
            if m:
                name, running, exit_code, oom = m.groups()
                level = 'CRITIQUE' if oom.lower() == 'true' else ('ALERTE' if running.lower() == 'false' else 'INFO')
                typ = 'docker.oom' if oom.lower() == 'true' else 'docker.container.state'
                human = f"Conteneur {name} : running={running}, exit={exit_code}, OOM={oom}"
                self.emit(source, 'DOCKER', level, typ, human, p,
                          service=name, exit_code=exit_code, event_key='docker-state:' + name)
                return True
        if p['program'] == 'Home_server-DOCKER':
            # docker events brut : conservé dans brut.log, les événements réellement utiles
            # sont traduits via les marqueurs SECURITY du collecteur d'état.
            return True
        return False

    def handle_er605(self, p: dict[str, Any], source: str) -> bool:
        if source != 'ER605':
            return False
        msg = p['message']
        low = msg.lower()
        if 'wireguard' in low or ' vpn' in low:
            category, typ = 'WireGuard', 'wireguard.event'
        elif any(x in low for x in ('acl', 'firewall', 'blocked', 'denied')):
            category, typ = 'PARE-FEU', 'er605.event'
        else:
            category, typ = 'SYSTEME', 'er605.event'
        level = 'ALERTE' if any(x in low for x in ('failed', 'denied', 'error', 'down')) else 'INFO'
        self.emit(source, category, level, typ, msg[:500], p, event_key='er605:' + hashlib.sha1(msg.encode()).hexdigest()[:12])
        return True

    def handle_generic_categories(self, p: dict[str, Any], source: str) -> bool:
        program, msg = p['program'].lower(), p['message']
        low = msg.lower()
        if 'nginx' in program:
            level = 'ALERTE' if 'error' in program or p['severity'] <= 3 else 'INFO'
            typ = 'nginx.error' if level == 'ALERTE' else 'nginx.access'
            self.emit(source, 'NGINX', level, typ, msg[:500], p, event_key='nginx:' + hashlib.sha1(msg.encode()).hexdigest()[:12])
            return True
        if 'pteroq' in program or 'pterodactyl' in low:
            self.emit(source, 'PTERO', 'INFO', 'ptero.event', msg[:500], p, event_key='ptero:' + hashlib.sha1(msg.encode()).hexdigest()[:12])
            return True
        if 'wireguard' in program or 'wireguard' in low:
            level = 'ALERTE' if any(x in low for x in ('fail', 'error', 'denied')) else 'INFO'
            self.emit(source, 'WireGuard', level, 'wireguard.event', msg[:500], p, event_key='wg:' + hashlib.sha1(msg.encode()).hexdigest()[:12])
            return True
        return False

    def handle_custom_rules(self, p: dict[str, Any], source: str) -> bool:
        for rule, rx in self.rules:
            if not rx.search(p['message']):
                continue
            template = rule.get('message', '{message}')
            try:
                human = template.format(message=p['message'], source=source)
            except (KeyError, ValueError):
                human = p['message']
            self.emit(source, rule.get('category', 'SYSTEME'), rule.get('level', 'INFO'),
                      rule.get('type', rule.get('id', 'generic.alert')), human[:500], p,
                      event_key='rule:' + str(rule.get('id', 'custom')) + ':' + hashlib.sha1(p['message'].encode()).hexdigest()[:10])
            return True
        return False

    def process(self, line: str) -> None:
        if not line.strip():
            return
        p = parse_raw(line)
        source = self.source_alias(p['host'])
        msg = p['message']

        # Ordre volontaire : états réseau/pare-feu d'abord, puis événements applicatifs.
        if self.handle_conntrack(p, source):
            return
        if self.handle_firewall(p, source):
            return
        if self.handle_etat_service(p, source):
            return
        if self.handle_ssh(p, source):
            return
        if self.handle_minecraft(p, source):
            return
        if self.handle_crowdsec(p, source):
            return
        if self.handle_docker(p, source):
            return
        if self.handle_er605(p, source):
            return
        if self.handle_generic_categories(p, source):
            return
        if self.handle_custom_rules(p, source):
            return

        # Generic SYSTEME : on conserve une ligne humaine, sauf bavardage systemd déjà filtré.
        if 'Home_server-etat.service' not in msg:
            level = 'ALERTE' if int(p.get('severity', 6)) <= 3 else 'INFO'
            typ = 'generic.alert' if level == 'ALERTE' else 'system.info'
            self.emit(source, 'SYSTEME', level, typ, msg[:500], p,
                      event_key='generic:' + hashlib.sha1((source + msg).encode()).hexdigest()[:12])

    def flush_state(self, force: bool = False) -> None:
        now = time.monotonic()
        if not self.dirty or (not force and now - self.last_state_write < 2):
            return
        # Les valeurs monotonic internes n'ont pas vocation à être interprétées comme timestamps.
        # Elles sont retirées avant persistance.
        persisted = json.loads(json.dumps(self.state))
        for bucket in ('firewall', 'scan', 'ssh_fail'):
            for item in persisted.get(bucket, {}).values():
                item.pop('_mono', None)
        # Les heartbeats sont uniquement une temporisation de session.
        persisted['heartbeats'] = {}
        atomic_json(self.state_path, persisted, 0o640)
        self.dirty = False
        self.last_state_write = now


def tail(engine: Engine, from_start: bool = False) -> None:
    path = Path(engine.cfg['input_log'])
    poll = float(engine.cfg.get('poll_interval_seconds', 0.25))
    fh = None
    inode = None
    offset = 0

    while RUNNING:
        try:
            st = path.stat()
        except FileNotFoundError:
            engine.expire_probes()
            engine.flush_state()
            time.sleep(poll)
            continue

        if fh is None or inode != st.st_ino:
            if fh:
                fh.close()
            fh = path.open('r', encoding='utf-8', errors='replace')
            inode = st.st_ino
            cursor = engine.state.get('input_cursor', {})
            if from_start:
                fh.seek(0)
            elif int(cursor.get('inode', -1)) == inode and 0 <= int(cursor.get('offset', 0)) <= st.st_size:
                fh.seek(int(cursor.get('offset', 0)))
            else:
                # Premier démarrage : partir de la fin pour ne pas retraiter tout l'historique.
                fh.seek(0, os.SEEK_END)
            offset = fh.tell()
            from_start = True  # Après rotation, lire le nouveau fichier depuis son début.

        line = fh.readline()
        if line:
            offset = fh.tell()
            engine.process(line)
            engine.state['input_cursor'] = {'inode': inode, 'offset': offset}
            engine.dirty = True
        else:
            engine.expire_probes()
            engine.flush_state()
            try:
                current = path.stat()
                if current.st_ino == inode and current.st_size < offset:
                    fh.seek(0)
                    offset = 0
            except FileNotFoundError:
                pass
            time.sleep(poll)

    if fh:
        fh.close()
    engine.expire_probes()
    engine.flush_state(force=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-start', action='store_true', help='Lire brut.log depuis le début (tests uniquement).')
    ap.add_argument('--line', help='Normaliser une seule ligne et quitter.')
    args = ap.parse_args()
    cfg = load_json(CONFIG_PATH, {})
    if not cfg:
        raise SystemExit(f'Configuration absente: {CONFIG_PATH}')
    identities = load_json(IDENTITIES_PATH, {})
    rules = load_json(RULES_PATH, {'rules': []})
    engine = Engine(cfg, identities, rules)
    if args.line is not None:
        engine.process(args.line)
        engine.expire_probes()
        engine.flush_state(force=True)
        return 0
    tail(engine, args.from_start)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
