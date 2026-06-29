# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目概述

**AIOps** = 多路召回 RAG 知识库 + Linux 主机实时监控

为运维团队提供：
1. **知识库查询** — 文档检索 + 服务拓扑分析（ES + Neo4j + Rerank）
2. **主机状态监控** — 实时 CPU/内存/磁盘/负载指标（Zabbix API）
3. **故障影响分析** — 主机故障时受影响的服务链路（Neo4j 多跳推理）

---

## 核心功能

### 1. RAG 知识库 (`rag/`)

**多路召回流水线：**
```
用户查询 → LLM 改写 + 实体提取
         → ES BM25 (IK 分词) + ES 向量 (Qwen3-Embedding-8B)
         → Neo4j 图拓扑 (Service/Host/Port/Cluster)
         → 集群感知扩展 → 二次检索
         → RRF 融合 → Rerank (Qwen3-Reranker-8B) → LLM 生成答案
```

**API 端点：**
- `POST /api/v1/query` — 知识库问答
- `GET /api/v1/topology?service_id=` — 服务拓扑
- `GET /api/v1/impact?host_id=` — 主机故障影响分析
- `GET /api/v1/host/resolve?ip=` — IP→host_id 解析
- `GET /api/v1/health` — 健康检查

**CLI 工具：**
- `aiops-query query '<问题>'` — 知识库问答
- `aiops-query impact <host_id>` — 影响分析
- `aiops-query topology <service_id>` — 拓扑查询

### 2. 主机监控 (`host-access/`)

**Zabbix JSON-RPC 客户端：**
- 按 IP 查主机（`get_host_by_ip`）
- 获取监控项（`get_host_items`）
- 取最新指标（`get_latest_metrics`）
- 网卡自动发现（`discover_network_interfaces`）

**CLI 工具：**
- `host-query status <ip>` — 主机实时状态（CPU/内存/磁盘/负载）+ host_id
- `host-query items <ip>` — 该主机所有监控项

**支持的主机类型：**
- Linux：`system.cpu.util[]`、`vm.memory.size[pavailable]`、`vfs.fs.size[/,pused]`
- Windows：`vm.memory.util`、`vfs.fs.size[C:,pused]`
- 自动处理 pfree→pused 转换

### 3. OpenClaw Agent 编排

**路由规则：**
- 含 IP 地址的主机查询 → `linux` agent（使用 host-query + aiops-query）
- 含 host_id 的拓扑查询 → `rag` skill（使用 aiops-query impact）
- 文档/SOP 相关 → `rag` skill（使用 aiops-query query）

**linux agent 工作流：**
```
用户问题 → 提取 IP → host-query status <IP> → 获取指标 + host_id
                    → aiops-query impact <host_id> → 获取拓扑影响
                    → 融合回答
```

---

## 常用命令

### 启动服务

```bash
# 启动 RAG 知识库（ES + Neo4j + API）
cd rag && docker compose up -d

# 启动 host-access（可选，目前直接调用 Zabbix API）
cd ../host-access && docker compose up -d
```

### 运行测试

```bash
# RAG 测试
cd rag && pytest

# host-access 测试
cd host-access && PYTHONPATH=. pytest

# 集成测试
cd .. && PYTHONPATH=host-access pytest tests/test_integration.py

# 单个测试
cd rag && pytest tests/test_graph_resolver.py::test_resolve_host_by_ip_found -v
```

### 验证服务

```bash
# 健康检查
curl http://localhost:8001/api/v1/health

# 知识库查询
curl -X POST http://localhost:8001/api/v1/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "nginx 502 怎么排查"}'

# 主机状态
host-query status 10.33.17.100

# 影响分析
aiops-query impact host_es_master_01
```

### 索引管理

```bash
# 增量索引
cd rag && docker exec rag-api python3 /app/scripts/index-docs.py

# 全量索引
cd rag && docker exec rag-api python3 /app/scripts/index-docs.py --full

# 单文件索引
cd rag && docker exec rag-api python3 /app/scripts/index-docs.py --file wiki/services/svc_nginx/tech-arch.md

# 加载拓扑
cd rag && docker exec rag-api python3 /app/scripts/load-topology.py /app/wiki/topology/call-graph.yml
```

---

## 架构

### 目录结构

```
workspace-shared/aiops/
├── rag/                          # RAG 知识库
│   ├── app/                      # FastAPI 应用
│   │   ├── api/routes.py         # API 端点
│   │   ├── retrievers/           # 检索器（ES/向量/图）
│   │   ├── router/               # 查询路由（改写/意图/cypher）
│   │   ├── reranker/             # Rerank 模型
│   │   └── config.py             # 配置（pydantic-settings）
│   ├── scripts/                  # 运维脚本
│   ├── wiki/                     # 知识文档 + 拓扑
│   ├── skills/                   # OpenClaw skill
│   │   └── aiops-query           # CLI 工具
│   └── tests/                    # pytest 测试
├── host-access/                  # 主机监控服务
│   ├── zabbix/client.py          # Zabbix JSON-RPC 客户端
│   ├── relation/host_resolver.py # IP→host_id 关联
│   ├── cli/host_query.py         # CLI 工具
│   ├── config.py                 # 配置（Zabbix 凭证）
│   └── tests/                    # pytest 测试
├── docs/superpowers/
│   ├── specs/                    # 设计文档
│   ├── plans/                    # 实施计划
│   └── review-artifacts/         # 评审可视化
└── README.md
```

### 数据流

**典型查询："10.33.17.100 负载多少？影响什么服务？"**

```
用户 → main agent → linux agent
                    ├─ host-query status 10.33.17.100
                    │     ├─ Zabbix API 取实时指标
                    │     └─ rag /host/resolve → host_id
                    ├─ aiops-query impact host_es_master_01
                    │     └─ Neo4j 多跳影响分析
                    └─ 融合回答
```

### 配置

**环境变量：**
- `rag/.env` — ES/Neo4j/LLM 配置
- `host-access/.env` — Zabbix 凭证（权限 600）

**关键配置项：**
```python
# rag/app/config.py
es_url = "http://elastic:rag-password@elasticsearch:9200"
neo4j_uri = "bolt://neo4j:rag-password@neo4j:7687"

# host-access/config.py
zabbix_url = "http://f.oetsky.com/api_jsonrpc.php"
zabbix_user = "sunweini"
rag_api_url = "http://localhost:8001/api/v1"
```

---

## 后续计划

### 二期功能

- [ ] 前端界面（对话 UI / 主机看板）
- [ ] Zabbix 告警接入
- [ ] 更多指标（inode、TCP 连接、进程存活）
- [ ] host-access 可扩 SSH 诊断（受 OpenClaw 安全规则约束）

### 已知限制

- **cluster 数据为空** — topology 中 `clusters: 0`，`get_host_cluster` 函数空跑
- **rag-wiki 遗留** — `~/.openclaw/workspace-shared/rag-wiki/` 是空目录，应清理
- **CPU idle 匹配** — 已修复 `system.cpu.util[]` vs `system.cpu.util[,idle]` 区分

---

## 开发规范

### 硬规则

1. **单次 CLI 调用** — 禁止生成脚本串联查询
2. **禁止 SSH** — 只能通过 Zabbix API 获取指标
3. **禁止 kubectl** — 不查询 K8s Pod，只查 Zabbix 监控项
4. **不编造数据** — 无数据时明确报错

### 测试要求

- 所有新功能必须有 pytest 测试
- mock 外部依赖（Zabbix/rag HTTP）
- 集成测试验证端到端流程

### 提交规范

- 提交到 `main` 分支（当前允许）
- 提交信息格式：`feat: ...` / `fix: ...` / `docs: ...`
- 包含 Co-Authored-By: Claude <noreply@anthropic.com>
