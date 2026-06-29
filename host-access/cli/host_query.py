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
        # 注意：Zabbix item key 格式因主机/版本/OS 而异，使用模糊匹配
        item_key_patterns = [
            "system.cpu.util",           # CPU 使用率 (匹配 system.cpu.util 和 system.cpu.util[])
            "vm.memory.size[pavailable]",  # 内存可用率 (Linux)
            "vm.memory.util",            # 内存使用率 (Windows)
            "vfs.fs.size[/,pused]",      # 磁盘使用率（Linux 根分区）
            "vfs.fs.dependent.size[/,pused]",  # 磁盘使用率（Linux 新格式）
            "vfs.fs.size[/,pfree]",      # 磁盘可用率（Linux 备用）
            "vfs.fs.size[C:,pused]",     # 磁盘使用率（Windows C 盘）
            "vfs.fs.size[D:,pused]",     # 磁盘使用率（Windows D 盘）
            "system.cpu.load[all,avg1]", # load1 (Linux all)
            "system.cpu.load[percpu,avg1]", # load1 (Linux percpu)
            "agent.ping",                # 在线状态
        ]

        # 网卡自动发现（暂不显示网络流量）
        # ifaces = client.discover_network_interfaces(hostid)
        # primary_iface = "eth0" if "eth0" in ifaces else (ifaces[0] if ifaces else None)

        metrics = client.get_latest_metrics(hostid, item_key_patterns)

        # 3. rag: IP → host_id
        resolved = resolver.resolve(ip)
        host_id = resolved["host_id"] if resolved else ""
        host_name_rag = resolved.get("host_name", "") if resolved else ""

        # 4. 格式化输出
        online = "online" if host.get("available") == "1" else "offline"
        cpu = metrics.get("system.cpu.util", "N/A")
        # 内存：Linux 用 pavailable，Windows 用 memory.util
        mem = metrics.get("vm.memory.size[pavailable]",
                metrics.get("vm.memory.util", "N/A"))
        # 磁盘：尝试多种 key 格式（Linux 根分区 / Windows C 盘）
        disk_raw = metrics.get("vfs.fs.dependent.size[/,pused]",
                metrics.get("vfs.fs.size[/,pused]",
                metrics.get("vfs.fs.size[C:,pused]",
                metrics.get("vfs.fs.size[D:,pused]", None))))
        # 如果使用率没有，尝试可用率并转换
        if disk_raw is None:
            pfree = metrics.get("vfs.fs.size[/,pfree]")
            if pfree and pfree != "N/A":
                try:
                    disk_raw = str(round(100 - float(pfree), 2))
                except:
                    pass
        disk = disk_raw if disk_raw else "N/A"
        # 负载：尝试两种格式（仅 Linux）
        load = metrics.get("system.cpu.load[all,avg1]",
                metrics.get("system.cpu.load[percpu,avg1]", "N/A"))

        print(f"Host: {host_name_rag or zabbix_name} ({ip})")
        print(f"Zabbix: {online}")
        print(f"Zabbix name: {zabbix_name}")
        print(f"CPU: {cpu}%    Memory avail: {mem}%")
        print(f"Disk /: {disk}% used")
        print(f"Load1: {load}")
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
