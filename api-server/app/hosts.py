"""Host status aggregation — combines Neo4j topology with Zabbix metrics."""

import os
from app.zabbix.client import ZabbixClient

# Item key patterns for metrics extraction
ITEM_KEY_PATTERNS = [
    "system.cpu.util[]",
    "system.cpu.util",
    "vm.memory.size[pavailable]",
    "vm.memory.util",
    "vfs.fs.size[/,pused]",
    "vfs.fs.dependent.size[/,pused]",
    "vfs.fs.size[C:,pused]",
    "system.cpu.load[all,avg1]",
    "system.cpu.load[percpu,avg1]",
]

# Singleton client
_client = None


def get_client():
    global _client
    if _client is None:
        _client = ZabbixClient()
    return _client


def get_host_metrics(ip: str) -> dict:
    """Get real-time metrics for a host by IP from Zabbix."""
    client = get_client()
    try:
        host = client.get_host_by_ip(ip)
        if not host:
            return {"available": False, "metrics": {}}

        raw = client.get_latest_metrics(host["hostid"], ITEM_KEY_PATTERNS)

        # Extract metrics with fallbacks
        cpu = raw.get("system.cpu.util[]", raw.get("system.cpu.util"))
        mem = raw.get("vm.memory.size[pavailable]", raw.get("vm.memory.util"))
        disk = raw.get("vfs.fs.dependent.size[/,pused]",
                 raw.get("vfs.fs.size[/,pused]",
                 raw.get("vfs.fs.size[C:,pused]")))
        load = raw.get("system.cpu.load[all,avg1]",
                 raw.get("system.cpu.load[percpu,avg1]"))

        def to_float(v):
            if v is None or v == "N/A":
                return None
            try:
                return round(float(v), 2)
            except (ValueError, TypeError):
                return None

        return {
            "available": host.get("available") == "1",
            "metrics": {
                "cpu": to_float(cpu),
                "memory": to_float(mem),
                "disk": to_float(disk),
                "load1": to_float(load),
            }
        }
    except Exception as e:
        print(f"Zabbix metrics error for {ip}: {e}")
        return {"available": False, "metrics": {}}
    finally:
        client.logout()
