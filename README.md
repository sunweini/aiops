# AIOps

多路召回 RAG + Linux 主机实时监控。

- `rag/` — 知识库（ES + Neo4j + Rerank）
- `host-access/` — 主机实时指标取数服务（Zabbix）
- `agents/` — OpenClaw agent 定义

## Quick Start

```bash
cd rag && docker compose up -d
cd ../host-access && docker compose up -d
```
