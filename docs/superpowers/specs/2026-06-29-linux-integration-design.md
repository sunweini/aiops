# AIOps 一期：Linux 接入设计

**日期**: 2026-06-29
**状态**: 设计稿（评审修复中）
**作者**: brainstorming 会话产出
**评审**: 2026-06-29 可视化评审，修复 7 个问题（2 高危 + 3 中危 + 2 低危）

---

## 1. 背景与目标

### 1.1 现状

AIOps 知识库 RAG（`rag/`）已上线，提供：

- 文档检索（ES BM25 + 向量 + Rerank）
- 服务/主机/端口拓扑查询（Neo4j 图）
- 现有接入方式：`aiops-query` CLI + OpenClaw skill（硬规则：单次 CLI 调用，禁止脚本串联）

拓扑中 Host 节点已有 `ip` 字段、`host_ip` 唯一约束，及 `get_host_services` / `get_host_impact` 等按 host_id 查询能力。但 `wiki/hosts/` 主机文档目录为空。

**已知限制（🟡 评审标注）**：topology 中 `clusters: 0`，cluster 数据尚未录入。`get_host_cluster` / `get_service_cluster` 函数存在但当前空跑。一期不依赖 cluster 扩展能力，后续补充 cluster 数据后可启用。

RAG 是**纯静态知识库**：查文档、查拓扑。无任何实时主机状态能力。

### 1.2 一期目标

给 AIOps 加 **Linux 主机接入**，让运维能查询主机的**实时运行状态 + 拓扑关联**：

- 输入主机 IP → 返回实时指标（CPU/内存/磁盘/网络/负载/在线状态）+ 该主机上跑哪些服务 + 故障影响
- 不自建采集，复用现有 Zabbix 监控
- 不落库：实时数据即时取，不入 ES/Neo4j
- 前端界面归二期，一期只做后端能力 + agent 编排

### 1.3 非目标（明确排除）

| 排除项 | 原因 / 归属 |
|--------|------------|
| 告警接入 | 语义复杂（严重度/确认态），二期 |
| SSH 远程诊断执行 | 安全面大，未来 |
| 前端界面 | 独立工程，二期 |
| rag 升级为 MCP server | 改动大，超范围，rag 维持 CLI+skill |
| 指标落库（写 ES/Neo4j） | 实时数据不入知识库 |
| Zabbix 采集层建设 | 复用现有 Zabbix，不自建 |

---

## 2. 核心决策（会话锁定项）

| 决策点 | 选定 | 理由 |
|--------|------|------|
| 接入范围 | D — 纳管元数据 + 基础指标 | 一期"简单" |
| 采集方式 | A — 接 Zabbix | 复用现有监控，不自建 |
| Zabbix 接法 | A — API 直连，不落库 | 实时数据不入知识库 |
| 关联键 | IP | 主机名对不上，IP 可对上 |
| 能力范围 | B — 主机状态 + 拓扑关联，告警留二期 | IP↔服务关联数据已有，价值最高 |
| 架构 | A — OpenClaw 多 agent 编排，新建 linux agent | 融合在 agent 层，取数层薄 |
| 新 agent | 新建 linux agent | 职责清晰，长期可扩 |
| 取数层归属 | B — host-access 独立服务 | rag 回归纯知识库，不碰实时指标 |
| 接入范式 | A — host-access 走 CLI + skill（同 rag 模式） | 零新范式，跟 rag 一致 |
| 关联位置 | B — host-access 内部用 IP 交叉 rag 拓扑，返回附带 host_id | rag 零改动，关联复杂度归 host-access |
| 前端 | X — 归二期 | 一期专注后端 |
| 目录结构 | aiops 项目根 = `workspace-shared/aiops/`；rag 下沉为子模块；一期顺手重构 | 趁此次立对骨架 |

---

## 3. 架构

### 3.1 总体

```
┌─────────────────────── OpenClaw 多 Agent 平台 ───────────────────────┐
│                                                                     │
│   用户自然语言                                                       │
│        │                                                            │
│        ▼                                                            │
│   ┌─────────┐  分发   ┌──────────────┐                              │
│   │  main   │ ──────► │ linux agent  │  ← 新建（workspace-linux）   │
│   │ (协调)   │         └──────┬───────┘                              │
│   └─────────┘                │ host-status skill 编排              │
│                              │                                     │
│              ┌───────────────┼───────────────┐                      │
│              ▼               ▼               ▼                      │
│      host-query CLI    aiops-query CLI   (他 agent)                 │
│              │               │                                      │
│      ┌───────▼───────┐  ┌────▼────────────┐  └────────────────┐     │
│      │ host-access   │  │ rag (知识库)     │  │ ES + Neo4j     │     │
│      │ (独立服务)     │  │ FastAPI:8001    │  │ (静态拓扑/文档) │     │
│      │ Zabbix client  │  │ CLI: aiops-query│  └────────────────┘     │
│      │ + IP↔host_id   │  └─────────────────┘                         │
│      │   关联         │                                              │
│      └───────┬───────┘                                               │
│              │                                                       │
│              ▼                                                       │
│      ┌───────────────┐                                               │
│      │   Zabbix      │  ← JSON-RPC API（只读取 host/指标）           │
│      │   API         │                                               │
│      └───────────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 职责边界

| 组件 | 职责 | 不做 |
|------|------|------|
| **rag** | 文档检索 + 拓扑查询（服务/主机/端口/调用/影响） | 不碰 Zabbix、不取实时指标、不落指标 |
| **host-access** | Zabbix API 调用 + IP↔host_id 关联 + CLI 暴露 | 不落库、不做告警 |
| **linux agent** | 编排：调 host-query 取状态 + aiops-query 取拓扑 → 融合回答 | 不碰 Zabbix 凭证、不写取数逻辑 |
| **Zabbix** | 监控采集 + 指标存储（原有） | — |

### 3.3 数据流（典型查询）

```
用户："10.33.17.100 现在负载多少？影响什么服务？"
  │
  ▼ main 协调 → 分发给 linux agent
  │
linux agent（host-status skill）
  │
  ├─ 调 host-query status 10.33.17.100
  │     └─ host-access：
  │          Zabbix API 取该 IP host 的实时指标
  │          + 按 IP 查 rag 拓扑，找到 host_id（如 host_es_master_01）
  │          → 返回 {指标..., host_id: host_es_master_01}
  │
  ├─ 拿到 host_id，调 aiops-query impact host_es_master_01
  │     └─ rag：Neo4j 多跳影响分析，返回受影响服务 + 下游
  │
  └─ 融合：状态 + 影响服务 → 组织答案返回
```

---

## 4. 目录结构（重构后）

```
workspace-shared/aiops/                    ← AIOps 项目根（新建）
├── README.md
├── CLAUDE.md                              ← 项目级指引
├── docs/
│   ├── 维护指南.md                        ← 从 rag/docs/ 迁入
│   └── superpowers/
│       └── specs/
│           ├── 2026-05-30-aiops-rag-design.md        ← 从 rag 迁入
│           └── 2026-06-29-linux-integration-design.md ← 本文档
├── rag/                                   ← 现 rag 内容下沉到此
│   ├── app/                               ← FastAPI（知识库，不变）
│   │   ├── api/routes.py
│   │   ├── retrievers/
│   │   ├── router/
│   │   ├── indexer/
│   │   ├── reranker/
│   │   └── config.py
│   ├── scripts/                           ← 含 aiops-query CLI
│   ├── wiki/                              ← 知识文档 + 拓扑
│   ├── skills/                            ← rag 的 SKILL.md
│   ├── tests/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── requirements.txt
├── host-access/                          ← 一期新增：独立取数服务
│   ├── README.md
│   ├── zabbix/
│   │   └── client.py                      ← Zabbix JSON-RPC client
│   ├── relation/
│   │   └── host_resolver.py              ← IP↔host_id 关联（查 rag 拓扑）
│   ├── cli/
│   │   └── host-query                     ← CLI（同 aiops-query 模式）
│   ├── config.py                          ← Zabbix 凭证（.env）
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── requirements.txt
└── agents/
    └── linux/                             ← linux agent 定义
        └── skills/
            └── host-status/
                └── SKILL.md              ← 编排：host-query + aiops-query
```

### 4.1 rag 路径影响

容器内路径不变（`/app/wiki` 等）。宿主侧 `./wiki` 相对位置随 rag 下沉一层，docker-compose 的 build context 跟随调整。硬编码检查：

- `scripts/index-docs.py`：`WIKI_DIR = "/app/wiki"` — 容器内路径，不变
- `app/api/routes.py`：`/app/wiki/...`、`/app/scripts/...` — 容器内，不变
- `docker-compose.yml`：`./wiki:/app/wiki`、`build: context: .` — 跟随 rag 下沉，相对路径仍正确

**CLI 路径适配（🔴 评审修复）**：

`aiops-query` CLI 的路径检测逻辑需更新，支持新旧两路：

```python
# skills/aiops-query 的 _cand 列表需追加新路径
for _cand in [
    os.path.expanduser("~/.openclaw/workspace-shared/aiops/rag"),  # 新路径
    os.path.expanduser("~/.openclaw/workspace-shared/rag"),        # 旧路径（兼容）
    "/root/.openclaw/workspace-shared/aiops/rag",
    "/root/.openclaw/workspace-shared/rag"
]:
```

**rag-wiki 位置澄清（🔴 评审修复）**：

当前 `~/.openclaw/workspace-shared/rag-wiki/` 是**遗留空目录**（仅 `hosts/` 子目录存在但为空）。实际 wiki 内容在 `rag/wiki/`。CLI 的 `WIKI_DIR` 应统一指向 `rag/wiki/`，废弃 `rag-wiki/` 目录。

**Skill 文件路径修复（🔴 评审修复）**：

rag 下沉后，`skills/SKILL.md` 和 `skills/aiops-query` 中的路径引用需同步更新：

| 文件 | 原路径 | 新路径 |
|------|--------|--------|
| `skills/SKILL.md` L25 | `~/.openclaw/skills/aiops-rag/aiops-query` | `~/.openclaw/workspace-shared/aiops/rag/skills/aiops-query` |
| `skills/SKILL.md` L109 | `~/.openclaw/skills/aiops-rag/templates/sop.md` | `~/.openclaw/workspace-shared/aiops/rag/skills/templates/sop.md` |
| `skills/SKILL.md` L116 | `~/.openclaw/skills/aiops-rag/templates/tech.md` | `~/.openclaw/workspace-shared/aiops/rag/skills/templates/tech.md` |
| `skills/SKILL.md` L123 | `~/.openclaw/skills/aiops-rag/templates/incident.md` | `~/.openclaw/workspace-shared/aiops/rag/skills/templates/incident.md` |
| `skills/aiops-query` L63-64 | `~/.openclaw/workspace-shared/rag` | 加 `aiops/rag` 到 `_cand` 列表 |
| `skills/aiops-query` L72 | `~/.openclaw/workspace-shared/rag-wiki` | `~/.openclaw/workspace-shared/aiops/rag/wiki` |

**OpenClaw skill 安装位置**：

当前 skill 安装在 `~/.openclaw/skills/aiops-rag/`（符号链接或复制）。rag 下沉后有两种选择：

| 方案 | 优点 | 缺点 |
|------|------|------|
| A) 保持 skill 在 `~/.openclaw/skills/aiops-rag/` | 零改动，OpenClaw 自动加载 | skill 与 rag 代码分离，版本可能不同步 |
| B) skill 跟随 rag 到 `aiops/rag/skills/` | 代码+skill 一体 | 需更新 OpenClaw 配置指向新路径 |

**推荐方案 A**：skill 保持在 `~/.openclaw/skills/aiops-rag/`，但 `SKILL.md` 内的路径引用改为绝对路径（指向 `aiops/rag/`）。这样 OpenClaw 加载逻辑不变，只需更新 `SKILL.md` 文本。

**结论**：rag 下沉仅移动目录位置，容器内路径零改动，宿主侧 docker-compose 仍相对自身目录，无需改路径。但 CLI 路径检测需适配新位置，rag-wiki 遗留目录需清理，skill 文件路径引用需同步更新。

### 4.2 host-access 配置

- 独立 docker 服务，独立端口（避开 rag 的 8001）
- Zabbix 凭证：`host-access/.env` → `config.py` 的 Settings（同 rag 模式）
- 调 rag 拓扑：HTTP 调 rag 的 `/api/v1/...`（按 IP 查需新增端点，见 5.2）

---

## 5. 组件设计

### 5.1 Zabbix client（`host-access/zabbix/client.py`）

- 协议：Zabbix JSON-RPC（`api_jsonrpc.php`）
- 认证：`user.login` 获取 token → 调用 → `user.logout`
- **只读**：仅 `host.get` / `item.get` / `history.get`，无写操作

核心方法：

| 方法 | 输入 | 输出 |
|------|------|------|
| `get_host_by_ip(ip)` | IP | Zabbix host 对象（hostid, name, status, available） |
| `get_host_items(hostid)` | hostid | 该主机监控 item 列表 |
| `get_latest_metrics(hostid, item_keys)` | hostid + 指标键 | 指标最新值 |

指标键（一期固定集，可配置，不开放任意选）：

```
system.cpu.util              # CPU 使用率
vm.memory.size[pavailable]   # 内存可用率
vfs.fs.size[/,pused]         # 根分区磁盘使用率
vfs.fs.size[/,pfree]         # 根分区可用
system.cpu.load[all,avg1]    # load1
net.if.in[eth0]              # 网络入流量
net.if.out[eth0]             # 网络出流量
agent.ping                   # 在线状态
```

**指标键配置优化（🟠 评审修复）**：

上述指标键中 `net.if.in[eth0]` / `net.if.out[eth0]` 假设网卡名为 `eth0`，实际生产主机可能使用 `bond0`、`ens33`、`enp0s3` 等。一期实现需支持**网卡自动发现**：

```python
# zabbix/client.py 新增方法
def discover_network_interfaces(self, hostid: str) -> list[str]:
    """返回该主机所有网络接口名，如 ['eth0', 'bond0']"""
    items = self.get_host_items(hostid)
    ifaces = []
    for item in items:
        if item['key_'].startswith('net.if.in[') or item['key_'].startswith('net.if.out['):
            iface = item['key_'].split('[')[1].rstrip(']')
            if iface not in ifaces:
                ifaces.append(iface)
    return ifaces
```

`status` 命令优先取 `eth0`，若不存在则取列表第一个。磁盘同理可扩展多挂载点（`/data`、`/var`），但一期仅根分区。

**Token 缓存优化（🟡 评审修复）**：

当前设计每次 CLI 调用都 `user.login` → 调用 → `user.logout`，增加延迟。建议 `client.py` 实现简单 TTL 缓存：

```python
class ZabbixClient:
    def __init__(self, url, user, password, token_ttl=900):
        self._token = None
        self._token_exp = 0
        self.token_ttl = token_ttl  # 15 分钟

    def _get_token(self):
        if time.time() < self._token_exp:
            return self._token
        self._token = self.login()
        self._token_exp = time.time() + self.token_ttl
        return self._token
```

CLI 进程退出时调用 `logout` 清理。同进程内多次调用复用 token。

### 5.2 IP↔host_id 关联（`host-access/relation/host_resolver.py`）

- host-access 持 rag 的 HTTP 地址
- 按 IP 查 rag 拓扑找 host_id

**rag 现有查询走 host_id，不走 IP**（`graph_retriever.py` 的 `get_host_services` / `get_host_impact` 都按 host_id）。

关联归属（Q11 锁定 B）：host-access 内部用 IP 交叉 rag 拓扑，返回附带 host_id。关联复杂度归 host-access，rag 仅加一个轻量端点，不直连 Neo4j（破坏 rag 作为唯一知识库访问点）。

实现：rag 加 `GET /api/v1/host/resolve?ip=<ip>` → 返回 host_id。host-access 调它拿 host_id，再交 agent 用 host_id 调 aiops-query。**这是 rag 一期唯一改动**（一个查询函数 + 一个端点）。

### 5.3 host-access CLI（`host-access/cli/host-query`）

同 `aiops-query` 模式（单次 CLI、禁止脚本串联）。命令：

| 命令 | 用途 | 示例 |
|------|------|------|
| `host-query status <ip>` | 主机实时状态 + host_id | `host-query status 10.33.17.100` |
| `host-query items <ip>` | 该主机所有监控项 | `host-query items 10.33.17.100` |

`status` 输出（结构化文本，agent 易读）：

```
Host: host_es_master_01 (10.33.17.100)           ← rag host_id (IP)
Zabbix: online                                   ← Zabbix agent.ping
Zabbix name: master-1                            ← Zabbix host.name（参考）
CPU: 12.3%    Memory avail: 45.2%
Disk /: 67.8% used
Load1: 1.24
Net eth0 in: 1.2MB/s out: 800KB/s
host_id: host_es_master_01   ← 用于后续调 aiops-query
```

** 评审修复：Zabbix name vs rag host_id 标注**：

Zabbix 返回的 `name`（如 "master-1"）与 rag `host_id`（如 "host_es_master_01"）**不同**。两者通过 IP 关联，但语义不同：
- `host_id` = rag 拓扑主键，用于 `aiops-query impact <host_id>`
- `zabbix_name` = Zabbix 侧主机名，仅供运维参考

输出格式已拆分两行标注来源，避免混淆。`host_id` 行保留用于下游 CLI 调用。

### 5.4 linux agent + skill

- 新建 OpenClaw agent `linux`，workspace `~/.openclaw/workspace-linux/`
- skill `host-status`（`agents/linux/skills/host-status/SKILL.md`）编排流程：

```
用户问主机状态/负载/影响
  │
  ├─ 提取 IP（从问题或拓扑查询）
  ├─ host-query status <ip> → 取实时指标 + host_id
  ├─ aiops-query impact <host_id> → 取故障影响（若用户问影响）
  └─ 融合组织答案
```

skill 硬规则（同 rag skill）：单次 CLI 调用，禁止脚本串联。

### 5.5 OpenClaw 配置改动

`~/.openclaw/openclaw.json` 需新增：

- agents 段加 `linux` agent，绑定 workspace-linux
- main 的路由规则加：主机状态/负载类查询 → linux agent

**路由分流规则（🔴 评审修复：解决 rag vs linux agent 冲突）**：

rag SKILL.md 已有路由规则 `"xx挂了" → impact <host_id>`，linux agent 也处理主机查询。需明确边界：

| 用户提问模式 | 路由目标 | 理由 |
|-------------|---------|------|
| 含 IP 地址（`10.33.17.100 负载多少`） | **linux agent** | 需实时指标，rag 无此能力 |
| 含 host_id（`host_es_master_01 影响什么`） | **rag skill** | 纯拓扑查询，rag 已完备 |
| 含主机名但无 IP（`master-1 怎么了`） | **linux agent** | 需先 Zabbix 解析 IP，rag 无主机名索引 |
| 文档/SOP 相关（`nginx 502 排查`） | **rag skill** | 纯知识库，不涉及实时状态 |
| 混合查询（`10.33.17.100 负载 + 影响`） | **linux agent** | 需融合实时 + 拓扑，linux agent 编排 |

**main 路由规则伪代码**：
```
if query contains IP address:
    route to linux agent
elif query contains host_id pattern (host_*):
    route to rag skill (impact/topology)
elif query is about docs/SOP/incident:
    route to rag skill (query)
else:
    route to rag skill (default)
```

**rag SKILL.md 需同步更新**：在路由决策表加一条"主机实时状态/含 IP 查询 → 转 linux agent"，避免 rag 尝试回答无实时数据的问题。

---

## 6. 错误处理

| 场景 | 处理 |
|------|------|
| Zabbix 不可达 | host-access 返回错误码 + 文案，agent 告知"监控暂不可用"，不编造数据 |
| IP 在 Zabbix 无 host | 返回 "未纳管主机"，agent 据此回答 |
| IP 在 rag 拓扑无 host_id | status 仍返回指标，host_id 置空；agent 说明"拓扑中未关联服务" |
| Zabbix token 过期 | client 自动 re-login 一次，再失败报错 |
| 指标无数据（item 缺失） | 该项标注 "无数据"，不报整体失败 |

---

## 7. 测试

- **Zabbix client**：mock Zabbix API 响应，测 `get_host_by_ip` / `get_latest_metrics`。pytest。
- **host_resolver**：mock rag HTTP，测 IP→host_id 解析 + 无匹配。
- **host-query CLI**：端到端，mock client，验证输出格式。
- **rag host/resolve 端点**：Neo4j 测试数据，按 IP 查 host_id。

现有 rag 测试在 `rag/tests/`（pytest），host-access 测试建 `host-access/tests/`。

---

## 8. 交付与验收

### 8.1 一期交付物

1. `aiops/` 项目骨架建立，rag 下沉为子模块
2. `host-access/` 独立服务：Zabbix client + IP↔host_id 关联 + CLI
3. rag 新增 `GET /api/v1/host/resolve?ip=` 端点
4. linux agent + host-status skill
5. OpenClaw 配置：linux agent 注册 + 路由

### 8.2 验收标准

- `host-query status <已知在线主机 IP>` 返回正确指标 + host_id
- `host-query status <未知 IP>` 返回 "未纳管"
- linux agent 能回答 "10.33.17.100 现在负载多少 + 影响什么服务"（状态 + 影响融合）
- Zabbix 不可达时 agent 不编造数据，明确报错
- rag 原有功能（文档检索、拓扑）无回归

---

## 9. 二期展望（非本期）

- 前端界面（对话 UI / 主机看板）
- Zabbix 告警接入
- 更多指标（inode、TCP 连接、进程存活）
- host-access 可扩 SSH 诊断（仍受 OpenClaw 安全规则约束）

---

## 附录 A：评审修订记录

| 编号 | 严重度 | 问题 | 修复位置 | 修复内容 |
|------|--------|------|---------|---------|
| #1 | 🔴 高危 | CLI 路径断裂 | §4.1 | 新增 CLI 路径适配段，`_cand` 列表支持新旧两路 |
| #2 |  中危 | rag-wiki 位置混乱 | §4.1 | 澄清 rag-wiki 为遗留空目录，应统一指向 `rag/wiki/` |
| #3 | 🟡 低危 | cluster 数据为空 | §1.1 | 新增"已知限制"标注，一期不依赖 cluster 能力 |
| #4 | 🟠 中危 | 指标键硬编码 | §5.1 | 新增网卡自动发现方法 + token TTL 缓存优化 |
| #5 |  中危 | Zabbix name vs host_id 混淆 | §5.3 | 输出格式拆分两行，明确标注来源 |
| #6 | 🟡 低危 | Token 无缓存 | §5.1 | 新增 token TTL 缓存方案（同进程复用） |
| #7 |  高危 | routing 冲突 | §5.5 | 新增路由分流规则表 + main 路由伪代码 + rag SKILL.md 同步更新 |

---

## 附录 B：会话决策溯源

本设计由 brainstorming 会话逐题锁定，决策点见第 2 节。关键转折：

- Q9 澄清"指标不落库 + rag 不碰实时数据" → host-access 独立
- Q10/Q11 确定沿用 rag 的 CLI+skill 范式 + 关联归 host-access，使 rag 零改动（仅加 resolve 端点）
