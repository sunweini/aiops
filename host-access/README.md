# host-access

Linux 主机实时指标取数服务。

- Zabbix JSON-RPC client（只读）
- IP → host_id 关联（查 rag 拓扑）
- CLI: `host-query status <ip>` / `host-query items <ip>`

## Quick Start

```bash
cp .env.example .env  # 编辑凭证
docker compose up -d
./cli/host-query status 10.33.17.100
```
