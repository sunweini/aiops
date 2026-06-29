"""host-query CLI — 主机实时状态查询。

Usage:
  host-query status <ip>    # 主机实时状态 + host_id
  host-query items <ip>     # 该主机所有监控项
"""

import sys
import os

# Add parent dir to path so config/zabbix/relation are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zabbix.client import ZabbixClient
from relation.host_resolver import HostResolver
from config import settings


def cmd_status(ip: str):
    """查询主机实时状态 + host_id。"""
    client = ZabbixClient()
    resolver = HostResolver(settings.rag_api_url)

    try:
        # 1. Zabbix: 按 IP 找 host
        host = client.get_host_by_ip(ip)
        if not host:
            print(f"Host: unknown ({ip})")
            print("Zabbix: 未纳管主机")
            print(f"host_id: ")
            return

        hostid = host["hostid"]
        zabbix_name = host["name"]

        # 2. Zabbix: 取指标
        item_keys = [
            "system.cpu.util",
            "vm.memory.size[pavailable]",
            "vfs.fs.size[/,pused]",
            "system.cpu.load[all,avg1]",
            "agent.ping",
        ]

        # 网卡自动发现
        ifaces = client.discover_network_interfaces(hostid)
        primary_iface = "eth0" if "eth0" in ifaces else (ifaces[0] if ifaces else None)

        if primary_iface:
            item_keys.append(f"net.if.in[{primary_iface}]")
            item_keys.append(f"net.if.out[{primary_iface}]")

        metrics = client.get_latest_metrics(hostid, item_keys)

        # 3. rag: IP → host_id
        resolved = resolver.resolve(ip)
        host_id = resolved["host_id"] if resolved else ""
        host_name_rag = resolved.get("host_name", "") if resolved else ""

        # 4. 格式化输出
        online = "online" if host.get("available") == "1" else "offline"
        cpu = metrics.get("system.cpu.util", "N/A")
        mem = metrics.get("vm.memory.size[pavailable]", "N/A")
        disk = metrics.get("vfs.fs.size[/,pused]", "N/A")
        load = metrics.get("system.cpu.load[all,avg1]", "N/A")

        print(f"Host: {host_name_rag or zabbix_name} ({ip})")
        print(f"Zabbix: {online}")
        print(f"Zabbix name: {zabbix_name}")
        print(f"CPU: {cpu}%    Memory avail: {mem}%")
        print(f"Disk /: {disk}% used")
        print(f"Load1: {load}")

        if primary_iface:
            net_in = metrics.get(f"net.if.in[{primary_iface}]", "N/A")
            net_out = metrics.get(f"net.if.out[{primary_iface}]", "N/A")
            print(f"Net {primary_iface} in: {net_in} out: {net_out}")

        print(f"host_id: {host_id}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


def cmd_items(ip: str):
    """查询主机所有监控项。"""
    client = ZabbixClient()
    try:
        host = client.get_host_by_ip(ip)
        if not host:
            print(f"未纳管主机：{ip}")
            return

        items = client.get_host_items(host["hostid"])
        print(f"Host: {host['name']} ({ip}) — {len(items)} items")
        for item in items:
            print(f"  {item['key_']:40} {item.get('lastvalue', 'N/A')}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.logout()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    arg = sys.argv[2]

    if cmd == "status":
        cmd_status(arg)
    elif cmd == "items":
        cmd_items(arg)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
