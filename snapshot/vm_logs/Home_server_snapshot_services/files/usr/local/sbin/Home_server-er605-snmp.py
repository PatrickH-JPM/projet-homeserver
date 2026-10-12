#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time

CONFIG = "/etc/Home_server-er605-snmp.json"
OUT = "/var/lib/Home_server-textfile/er605.prom"

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=8)

def snmpget(host, community, *oids):
    return run(["snmpget", "-v2c", "-c", community, "-t", "2", "-r", "0", "-On", host, *oids])

def snmpwalk(host, community, oid):
    return run(["snmpwalk", "-v2c", "-c", community, "-t", "2", "-r", "0", "-On", host, oid])

def integers(text):
    return [int(x) for x in re.findall(r"=\s+INTEGER:\s+(-?\d+)", text)]

rows = [
    f"Home_server_er605_collecte_timestamp_seconds {time.time()}",
    "Home_server_er605_reachable 0",
    "Home_server_er605_snmp_configured 0",
    "Home_server_er605_snmp_up 0",
    "Home_server_er605_cpu_available 0",
    "Home_server_er605_memory_available 0",
]

try:
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    host = cfg["host"]
    community = cfg["community"]

    rows[2] = "Home_server_er605_snmp_configured 1"

    test = snmpget(host, community, ".1.3.6.1.2.1.1.3.0")
    if test.returncode == 0:
        rows[1] = "Home_server_er605_reachable 1"
        rows[3] = "Home_server_er605_snmp_up 1"

        cpu = snmpwalk(host, community, ".1.3.6.1.2.1.25.3.3.1.2")
        cpu_values = integers(cpu.stdout)

        if cpu.returncode == 0 and cpu_values:
            cpu_percent = sum(cpu_values) / len(cpu_values)
            rows[4] = "Home_server_er605_cpu_available 1"
            rows.append(f"Home_server_er605_cpu_percent {cpu_percent:.2f}")

        mem = snmpget(
            host,
            community,
            ".1.3.6.1.2.1.25.2.3.1.4.1",
            ".1.3.6.1.2.1.25.2.3.1.5.1",
            ".1.3.6.1.2.1.25.2.3.1.6.1",
        )
        mem_values = integers(mem.stdout)

        if mem.returncode == 0 and len(mem_values) >= 3:
            allocation, total_units, used_units = mem_values[:3]
            total_bytes = allocation * total_units
            used_bytes = allocation * used_units
            memory_percent = used_bytes / total_bytes * 100 if total_bytes else 0

            rows[5] = "Home_server_er605_memory_available 1"
            rows.append(f"Home_server_er605_memory_percent {memory_percent:.2f}")
            rows.append(f"Home_server_er605_memory_used_bytes {used_bytes}")
            rows.append(f"Home_server_er605_memory_total_bytes {total_bytes}")

except Exception:
    pass

tmp = OUT + ".tmp"
with open(tmp, "w", encoding="ascii") as f:
    f.write("\n".join(rows) + "\n")

os.chmod(tmp, 0o644)
os.replace(tmp, OUT)
