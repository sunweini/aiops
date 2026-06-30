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
    """Extract metrics from items using the pattern matching logic."""
    result = {}
    for pattern in ITEM_KEY_PATTERNS:
        for item in items:
            key = item["key_"]
            # Special case: system.cpu.util[] must not match system.cpu.util[,idle]
            if pattern == "system.cpu.util[]":
                if key == "system.cpu.util[]":
                    result[pattern] = item.get("lastvalue", "N/A")
                    break
            # Exact match or prefix match
            elif key == pattern or key.startswith(pattern) or pattern in key:
                # Skip idle metrics when looking for CPU usage
                if pattern == "system.cpu.util" and "idle" in key:
                    continue
                result[pattern] = item.get("lastvalue", "N/A")
                break

    # Map to final metrics
    cpu = result.get("system.cpu.util[]", result.get("system.cpu.util"))
    mem = result.get("vm.memory.size[pavailable]", result.get("vm.memory.util"))
    disk = result.get("vfs.fs.dependent.size[/,pused]",
                      result.get("vfs.fs.size[/,pused]",
                                 result.get("vfs.fs.size[C:,pused]")))
    load = result.get("system.cpu.load[all,avg1]",
                      result.get("system.cpu.load[percpu,avg1]"))

    return {
        "cpu": _to_float(cpu),
        "memory": _to_float(mem),
        "disk": _to_float(disk),
        "load1": _to_float(load),
    }


def get_all_host_metrics() -> dict:
    """Get metrics for all hosts in batch (2 API calls total, with 60s cache)."""
    global _cache, _cache_time

    # Check cache first
    if _cache and (time.time() - _cache_time) < CACHE_TTL:
        return _cache

    client = get_client()
    try:
        # Batch query: get all hosts (1 API call)
        zabbix_hosts = client.get_all_hosts()

        # Build IP -> hostid mapping and hostid -> availability
        ip_to_hostid = {}
        hostid_to_avail = {}
        for h in zabbix_hosts:
            hostid_to_avail[h["hostid"]] = h.get("available", "1")
            for iface in h.get("interfaces", []):
                ip = iface.get("ip")
                if ip:
                    ip_to_hostid[ip] = h["hostid"]

        # Batch query: get all items (1 API call)
        all_items = client.get_all_items()

        # Group items by hostid
        items_by_host = {}
        for item in all_items:
            hosts = item.get("hosts", [])
            if hosts:
                hostid = hosts[0]["hostid"]
                if hostid not in items_by_host:
                    items_by_host[hostid] = []
                items_by_host[hostid].append(item)

        # Build result: IP -> metrics
        result = {}
        for ip, hostid in ip_to_hostid.items():
            available = hostid_to_avail.get(hostid, "1") == "1"
            items = items_by_host.get(hostid, [])
            metrics = _extract_metrics(items) if items else {}

            result[ip] = {
                "available": available,
                "metrics": metrics
            }

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
