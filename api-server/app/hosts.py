"""Host status aggregation — optimized batch query."""

import os
import time
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

# Simple in-memory cache (60 seconds TTL)
_cache = {}
_cache_time = 0
CACHE_TTL = 60


def get_client():
    global _client
    if _client is None:
        _client = ZabbixClient()
    return _client


def _to_float(v):
    """Convert value to float, return None if invalid."""
    if v is None or v == "N/A":
        return None
    try:
        return round(float(v), 2)
    except (ValueError, TypeError):
        return None


def _extract_metrics(items: list[dict]) -> dict:
    """Extract metrics from items list, handling multiple key variants.

    For disk metrics, we try to find (in order):
    1. vfs.fs.dependent.size[/,pused] - percent used (new format)
    2. vfs.fs.size[/,pused] - percent used (old format)
    3. vfs.fs.size[C:,pused] - Windows C: drive
    4. vfs.fs.size[/,pfree] - percent free, convert to used
    """
    cpu = None
    memory = None
    disk_used = None
    disk_free = None
    load = None

    for item in items:
        key = item.get("key_", "")
        value = item.get("lastvalue", "N/A")

        # Skip idle metrics
        if "idle" in key:
            continue

        # CPU usage
        if key.startswith("system.cpu.util") or key == "system.cpu.util[]":
            if cpu is None and value != "N/A":
                cpu = value

        # Memory available percentage
        elif key == "vm.memory.size[pavailable]":
            if memory is None and value != "N/A":
                memory = value

        # Disk percent used (root partition)
        elif key == "vfs.fs.dependent.size[/,pused]":
            if disk_used is None and value != "N/A":
                disk_used = value
        elif key == "vfs.fs.size[/,pused]":
            if disk_used is None and value != "N/A":
                disk_used = value
        elif key == "vfs.fs.size[C:,pused]":
            if disk_used is None and value != "N/A":
                disk_used = value

        # Disk percent free (fallback - convert to used)
        elif key == "vfs.fs.size[/,pfree]":
            if disk_free is None and value != "N/A":
                disk_free = value

        # Load average (1 minute)
        elif key == "system.cpu.load[all,avg1]" or key == "system.cpu.load[percpu,avg1]":
            if load is None and value != "N/A":
                load = value

    # Use disk_used if available, otherwise convert disk_free
    disk = disk_used
    if disk is None and disk_free is not None:
        try:
            disk = str(100 - float(disk_free))
        except (ValueError, TypeError):
            pass

    return {
        "cpu": _to_float(cpu),
        "memory": _to_float(memory),
        "disk": _to_float(disk),
        "load1": _to_float(load),
    }


def get_all_host_metrics() -> dict:
    """Get metrics for specific hosts from topology (2 targeted API calls).

    Only queries Zabbix for hosts in the rag-api topology, not all hosts.
    """
    global _cache, _cache_time

    # Check cache first
    if _cache and (time.time() - _cache_time) < CACHE_TTL:
        return _cache

    client = get_client()
    try:
        # Get target host IPs from rag-api topology
        import httpx
        import os
        rag_base = os.environ.get('RAG_API_URL', 'http://localhost:8001').rstrip('/')
        resp = httpx.get(f'{rag_base}/api/v1/topology/all', timeout=10)
        topo = resp.json()
        target_hosts = topo.get('hosts', [])  # [{id, name, ip}]

        # Extract IPs we care about
        target_ips = [h.get('ip') for h in target_hosts if h.get('ip')]
        if not target_ips:
            return {}

        # Build IP -> host info mapping from topology
        ip_to_info = {h['ip']: h for h in target_hosts if h.get('ip')}

        # API call 1: Get ONLY our target hosts from Zabbix
        zabbix_hosts = client.get_hosts_by_ips(target_ips)

        # Build hostid -> IP mapping (from Zabbix interfaces)
        hostid_to_ip = {}
        hostid_to_avail = {}
        for zh in zabbix_hosts:
            hostid = zh["hostid"]
            hostid_to_avail[hostid] = zh.get("available", "1")
            for iface in zh.get("interfaces", []):
                ip = iface.get("ip")
                if ip and ip in ip_to_info:
                    hostid_to_ip[hostid] = ip

        # API call 2: Get ONLY specific metrics for ONLY our target hosts
        # Filter to only the metric keys we need
        metric_keys = [
            "system.cpu.util",      # CPU usage
            "vm.memory.size",       # Memory
            "vfs.fs.dependent.size", # Disk (new Zabbix format)
            "vfs.fs.size",          # Disk (old Zabbix format)
            "system.cpu.load",      # Load
        ]
        all_items = client.get_items_by_hosts(list(hostid_to_ip.keys()), keys=metric_keys)

        # Group items by hostid
        items_by_host = {}
        for item in all_items:
            hosts = item.get("hosts", [])
            if hosts:
                hostid = hosts[0]["hostid"]
                if hostid not in items_by_host:
                    items_by_host[hostid] = []
                items_by_host[hostid].append(item)

        # Build result: IP -> metrics (only for hosts we care about)
        result = {}
        for hostid, ip in hostid_to_ip.items():
            available = hostid_to_avail.get(hostid, "1") == "1"
            items = items_by_host.get(hostid, [])
            metrics = _extract_metrics(items) if items else {}

            result[ip] = {
                "available": available,
                "metrics": metrics
            }

        # Also include offline hosts (not found in Zabbix)
        found_ips = set(hostid_to_ip.values())
        for ip in target_ips:
            if ip not in found_ips:
                result[ip] = {"available": False, "metrics": {}}

        # Update cache
        _cache = result
        _cache_time = time.time()

        return result
    except Exception as e:
        print(f"Zabbix batch metrics error: {e}")
        return {}
    finally:
        # Don't logout in batch mode - reuse token
        pass
