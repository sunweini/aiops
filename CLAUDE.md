# CLAUDE.md

AIOps 项目根。rag 为子模块，host-access 为独立服务。

## 目录结构
- `rag/` — 知识库（FastAPI + ES + Neo4j）
- `host-access/` — Zabbix 取数服务
- `agents/` — OpenClaw agent 定义
- `docs/superpowers/specs/` — 设计文档
- `docs/superpowers/plans/` — 实施计划

## 常用命令
```bash
cd rag && docker compose up -d          # 启动知识库
cd host-access && docker compose up -d  # 启动取数服务
cd rag && pytest                         # 运行测试
```
