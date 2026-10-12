#!/usr/bin/python3
"""Collecte rapide de l'état Home_server pour node_exporter textfile.

- Etat des services systemd et du pare-feu.
- Etat + ressources des conteneurs Docker.
- Métriques dédiées au conteneur Minecraft Pterodactyl.
- Contrôle TLS peu fréquent (60 s) pour ne pas alourdir la collecte 2 s.
"""
import json
import os
import re
import socket
import http.client
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path('/var/lib/Home_server-textfile/docker.prom')
STATE_DIR = Path('/var/lib/Home_server-state')
STATE = STATE_DIR / 'etat.json'
DOCKER_SOCK = '/var/run/docker.sock'


def quoted(value):
    return json.dumps(str(value), ensure_ascii=True)


def atomic_write(path, text, mode=0o644):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text, encoding='ascii')
    os.chmod(tmp, mode)
    os.replace(tmp, path)


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path, timeout=3):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def docker_json(path):
    conn = UnixHTTPConnection(DOCKER_SOCK)
    try:
        conn.request('GET', path, headers={'Host': 'localhost'})
        resp = conn.getresponse()
        body = resp.read()
        if resp.status < 200 or resp.status >= 300:
            raise RuntimeError(f'Docker API HTTP {resp.status}: {body[:200]!r}')
        return json.loads(body.decode('utf-8'))
    finally:
        conn.close()


def parse_started_at(value):
    if not value or value.startswith('0001-'):
        return None
    value = value.replace('Z', '+00:00')
    # datetime accepte les fractions longues sur les Python récents ; repli à 6 chiffres sinon.
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        value = re.sub(r'(\.\d{6})\d+', r'\1', value)
        return datetime.fromisoformat(value).timestamp()


def docker_cpu_percent(stats):
    cpu = stats.get('cpu_stats', {})
    pre = stats.get('precpu_stats', {})
    usage = cpu.get('cpu_usage', {})
    pre_usage = pre.get('cpu_usage', {})
    cpu_delta = float(usage.get('total_usage', 0)) - float(pre_usage.get('total_usage', 0))
    system_delta = float(cpu.get('system_cpu_usage', 0)) - float(pre.get('system_cpu_usage', 0))
    online = cpu.get('online_cpus') or len(usage.get('percpu_usage') or []) or 1
    if cpu_delta <= 0 or system_delta <= 0:
        return 0.0
    return (cpu_delta / system_delta) * float(online) * 100.0


def docker_network(stats):
    rx = tx = 0
    for item in (stats.get('networks') or {}).values():
        rx += int(item.get('rx_bytes', 0) or 0)
        tx += int(item.get('tx_bytes', 0) or 0)
    return rx, tx


def minecraft_container(inspect_obj):
    ports = (inspect_obj.get('NetworkSettings') or {}).get('Ports') or {}
    for bindings in ports.values():
        for binding in bindings or []:
            if str(binding.get('HostPort', '')) in {'49150', '9940'}:
                return True
    labels = ((inspect_obj.get('Config') or {}).get('Labels') or {})
    # Repli : les conteneurs Wings/Pterodactyl ont généralement des labels pterodactyl.
    if any('pterodactyl' in str(k).lower() or 'pterodactyl' in str(v).lower() for k, v in labels.items()):
        return True
    return False


def container_disk_bytes(inspect_obj, cache, now):
    cid = inspect_obj.get('Id', '')
    item = cache.get(cid, {})
    if now - float(item.get('checked', 0)) < 60 and 'bytes' in item:
        return int(item['bytes'])
    source = None
    for m in inspect_obj.get('Mounts') or []:
        if m.get('Destination') == '/home/container' and m.get('Source'):
            source = m['Source']
            break
    if not source:
        return int(item.get('bytes', 0))
    try:
        result = subprocess.run(['du', '-sb', '--', source], check=True, text=True,
                                capture_output=True, timeout=10)
        size = int(result.stdout.split()[0])
        cache[cid] = {'checked': now, 'bytes': size}
        return size
    except (OSError, ValueError, subprocess.SubprocessError):
        return int(item.get('bytes', 0))


def systemd_states(units):
    result = {}
    for unit in units:
        try:
            p = subprocess.run(['systemctl', 'is-active', unit], text=True,
                               capture_output=True, timeout=3)
            result[unit] = int(p.stdout.strip() == 'active')
        except (OSError, subprocess.SubprocessError):
            result[unit] = 0
    return result


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(obj):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_name(STATE.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=True), encoding='ascii')
    os.chmod(tmp, 0o600)
    os.replace(tmp, STATE)


def main():
    now = time.time()
    role = Path('/etc/Home_server-role').read_text().strip()
    previous = load_state()
    previous_containers = previous.get('containers', {})
    disk_cache = previous.get('disk_cache', {})
    current_containers = {}

    rows = [
        f'Home_server_collecte_timestamp_seconds {now}',
        'Home_server_etat_collector_up 1',
    ]

    # Services systemd réellement utiles à la supervision.
    common = ['ssh', 'rsyslog', 'prometheus-node-exporter']
    if role == 'host':
        units = common + ['Home_server-host-firewall']
        firewall_unit = 'Home_server-host-firewall'
    elif role == 'game':
        units = common + ['docker', 'crowdsec', 'crowdsec-firewall-bouncer',
                          'Home_server-firewall', 'wings']
        firewall_unit = 'Home_server-firewall'
    else:
        units = common + ['docker', 'crowdsec', 'crowdsec-firewall-bouncer',
                          'Home_server-firewall', 'nginx', 'pteroq', 'mariadb', 'redis-server']
        firewall_unit = 'Home_server-firewall'

    states = systemd_states(units)
    for unit, active in states.items():
        rows.append(f'Home_server_service_active{{service={quoted(unit)}}} {active}')
    rows.append(f'Home_server_firewall_active {states.get(firewall_unit, 0)}')

    # Docker n'existe pas sur l'hyperviseur dans l'architecture actuelle.
    minecraft = None
    if role != 'host' and os.path.exists(DOCKER_SOCK):
        try:
            containers = docker_json('/containers/json?all=1')
            for summary in containers:
                cid = summary['Id']
                obj = docker_json(f'/containers/{cid}/json')
                name = (obj.get('Name') or cid[:12]).lstrip('/')
                state = obj.get('State') or {}
                running = bool(state.get('Running'))
                current_containers[name] = running
                labels = f'{{container={quoted(name)}}}'
                rows.append(f'Home_server_container_running{labels} {int(running)}')
                rows.append(f'Home_server_container_restart_total{labels} {int(obj.get("RestartCount", 0) or 0)}')
                rows.append(f'Home_server_container_oom{labels} {int(bool(state.get("OOMKilled")))}')

                if name in previous_containers and bool(previous_containers[name]) != running:
                    subprocess.run([
                        'logger', '-t', 'Home_server-DOCKER',
                        f'SECURITY etat conteneur {name} running={running} '
                        f'exit={state.get("ExitCode")} OOM={state.get("OOMKilled")}'
                    ], check=False)

                stat = None
                if running:
                    try:
                        stat = docker_json(f'/containers/{cid}/stats?stream=false')
                    except Exception:
                        stat = None
                if stat:
                    cpu = docker_cpu_percent(stat)
                    mem = int((stat.get('memory_stats') or {}).get('usage', 0) or 0)
                    limit = int((stat.get('memory_stats') or {}).get('limit', 0) or 0)
                    rx, tx = docker_network(stat)
                    rows.append(f'Home_server_container_cpu_percent{labels} {cpu:.6f}')
                    rows.append(f'Home_server_container_memory_bytes{labels} {mem}')
                    rows.append(f'Home_server_container_memory_limit_bytes{labels} {limit}')
                    rows.append(f'Home_server_container_network_receive_bytes_total{labels} {rx}')
                    rows.append(f'Home_server_container_network_transmit_bytes_total{labels} {tx}')

                started = parse_started_at(state.get('StartedAt')) if running else None
                uptime = max(0.0, now - started) if started else 0.0
                rows.append(f'Home_server_container_uptime_seconds{labels} {uptime:.3f}')

                disk = container_disk_bytes(obj, disk_cache, now)
                if disk:
                    rows.append(f'Home_server_container_disk_bytes{labels} {disk}')

                if role == 'game' and minecraft_container(obj):
                    minecraft = {
                        'name': name, 'running': running, 'cpu': 0.0, 'mem': 0,
                        'limit': 0, 'rx': 0, 'tx': 0, 'uptime': uptime, 'disk': disk
                    }
                    if stat:
                        minecraft['cpu'] = docker_cpu_percent(stat)
                        minecraft['mem'] = int((stat.get('memory_stats') or {}).get('usage', 0) or 0)
                        minecraft['limit'] = int((stat.get('memory_stats') or {}).get('limit', 0) or 0)
                        minecraft['rx'], minecraft['tx'] = docker_network(stat)

            rows.append('Home_server_docker_collecte_ok 1')
        except Exception as exc:
            rows.append('Home_server_docker_collecte_ok 0')
            subprocess.run(['logger', '-p', 'user.warning', '-t', 'Home_server-etat',
                            'Collecte Docker impossible: ' + str(exc)[:300]], check=False)
    elif role != 'host':
        rows.append('Home_server_docker_collecte_ok 0')

    # Alias stable pour le serveur Minecraft, indépendant de l'UUID Docker.
    if role == 'game':
        if minecraft:
            rows.extend([
                f'Home_server_minecraft_running {int(minecraft["running"])}',
                f'Home_server_minecraft_cpu_percent {minecraft["cpu"]:.6f}',
                f'Home_server_minecraft_memory_bytes {minecraft["mem"]}',
                f'Home_server_minecraft_memory_limit_bytes {minecraft["limit"]}',
                f'Home_server_minecraft_network_receive_bytes_total {minecraft["rx"]}',
                f'Home_server_minecraft_network_transmit_bytes_total {minecraft["tx"]}',
                f'Home_server_minecraft_uptime_seconds {minecraft["uptime"]:.3f}',
                f'Home_server_minecraft_disk_bytes {minecraft["disk"]}',
                f'Home_server_minecraft_container_info{{container={quoted(minecraft["name"])}}} 1',
            ])
        else:
            # Pas de conteneur identifiable : état OFF explicite au lieu de No data.
            rows.extend([
                'Home_server_minecraft_running 0',
                'Home_server_minecraft_cpu_percent 0',
                'Home_server_minecraft_memory_bytes 0',
                'Home_server_minecraft_memory_limit_bytes 0',
                'Home_server_minecraft_network_receive_bytes_total 0',
                'Home_server_minecraft_network_transmit_bytes_total 0',
                'Home_server_minecraft_uptime_seconds 0',
                'Home_server_minecraft_disk_bytes 0',
            ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(OUT, '\n'.join(rows) + '\n')

    # Vérification certificat au plus une fois par minute.
    last_cert = float(previous.get('last_cert_check', 0) or 0)
    if now - last_cert >= 60:
        for cert in Path('/etc/Home_server-pki').glob('*.crt'):
            try:
                result = subprocess.run(['openssl', 'x509', '-enddate', '-noout', '-in', str(cert)],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    continue
                expiry = datetime.strptime(result.stdout.strip().split('=', 1)[1],
                                           '%b %d %H:%M:%S %Y %Z').replace(tzinfo=timezone.utc).timestamp()
                marker = Path('/var/lib/Home_server-textfile/tls-' + cert.name + '.alerte')
                due = (not marker.exists()) or now - marker.stat().st_mtime > 86400
                if expiry - now < 30 * 86400 and due:
                    marker.write_text('alerte')
                    subprocess.run(['logger', '-p', 'user.err', '-t', 'Home_server-TLS',
                                    'SECURITY certificat expire dans moins de 30 jours ' + cert.name], check=False)
            except Exception:
                pass
        previous['last_cert_check'] = now

    previous['containers'] = current_containers
    previous['disk_cache'] = disk_cache
    save_state(previous)


if __name__ == '__main__':
    main()
