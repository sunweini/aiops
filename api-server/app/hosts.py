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

# Separate caches for topology-based and Zabbix-based queries
_cache_topology = {}
_cache_topology_time = 0
_cache_zabbix = {}
_cache_zabbix_time = 0
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

        # Memory available percentage (Linux)
        elif key == "vm.memory.size[pavailable]":
            if memory is None and value != "N/A":
                memory = value

        # Memory usage percentage (Windows)
        elif key == "vm.memory.util":
            if memory is None and value != "N/A":
                # Windows reports usage %, convert to available %
                memory = str(100 - float(value))

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


def _is_vip_host(host_info: dict) -> bool:
    """Check if a host is a VIP (Virtual IP) host that should be excluded from monitoring."""
    name = (host_info.get('name') or '').lower()
    host_id = (host_info.get('id') or '').lower()
    # Filter out VIP hosts (case-insensitive)
    return 'vip' in name or 'vip' in host_id


def get_hosts_from_zabbix() -> dict:
    """Get all hosts directly from Zabbix (bypassing Neo4j topology).

    This ensures we always have the latest host list even if topology is outdated.
    """
    global _cache_zabbix, _cache_zabbix_time

    # Check cache first
    if _cache_zabbix and (time.time() - _cache_zabbix_time) < CACHE_TTL:
        return _cache_zabbix

    client = get_client()
    try:
        # Get all hosts from Zabbix
        all_zabbix_hosts = client.get_all_hosts()

        # Filter out VIP hosts
        all_zabbix_hosts = [h for h in all_zabbix_hosts if not _is_vip_host({
            'name': h.get('name', ''),
            'id': h.get('hostid', '')
        })]

        # Build hostid -> IP mapping
        hostid_to_ip = {}
        hostid_to_info = {}
        for zh in all_zabbix_hosts:
            hostid = zh["hostid"]
            for iface in zh.get("interfaces", []):
                ip = iface.get("ip")
                if ip:
                    hostid_to_ip[hostid] = ip
                    hostid_to_info[ip] = {
                        'hostid': hostid,
                        'name': zh.get('name', ''),
                        'available': zh.get("available", "1")
                    }
                    break

        if not hostid_to_ip:
            return {}

        # Get metrics for all hosts
        metric_keys = [
            "system.cpu.util",
            "vm.memory.size",       # Memory (Linux)
            "vm.memory.util",       # Memory (Windows)
            "vfs.fs.dependent.size", # Disk (new)
            "vfs.fs.size",          # Disk (old)
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

        # Build result
        result = {}
        for hostid, ip in hostid_to_ip.items():
            info = hostid_to_info.get(ip, {})
            available = info.get("available", "1") == "1"
            items = items_by_host.get(hostid, [])
            metrics = _extract_metrics(items) if items else {}

            result[ip] = {
                "available": available,
                "metrics": metrics,
                "name": info.get("name", "")
            }

        # Update cache
        _cache_zabbix = result
        _cache_zabbix_time = time.time()

        return result
    except Exception as e:
        print(f"Zabbix batch metrics error: {e}")
        return {}


def get_all_host_metrics() -> dict:
    """Get metrics for specific hosts from topology (2 targeted API calls).

    Only queries Zabbix for hosts in the rag-api topology, not all hosts.
    Automatically excludes VIP hosts from monitoring.
    """
    global _cache_topology, _cache_topology_time

    # Check cache first
    if _cache_topology and (time.time() - _cache_topology_time) < CACHE_TTL:
        return _cache_topology

    client = get_client()
    try:
        # Get target host IPs from rag-api topology
        import httpx
        import os
        rag_base = os.environ.get('RAG_API_URL', 'http://localhost:8001').rstrip('/')
        resp = httpx.get(f'{rag_base}/api/v1/topology/all', timeout=10)
        topo = resp.json()
        target_hosts = topo.get('hosts', [])  # [{id, name, ip}]

        # Filter out VIP hosts
        target_hosts = [h for h in target_hosts if not _is_vip_host(h)]

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
            "vm.memory.size",       # Memory (Linux)
            "vm.memory.util",       # Memory (Windows)
            "vfs.fs.dependent.size", # Disk (new)
            "vfs.fs.size",          # Disk (old)
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
        _cache_topology = result
        _cache_topology_time = time.time()

        return result
    except Exception as e:
        print(f"Zabbix batch metrics error: {e}")
        return {}
    finally:
        # Don't logout in batch mode - reuse token
        pass
