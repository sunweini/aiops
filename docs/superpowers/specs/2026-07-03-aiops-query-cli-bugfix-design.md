# aiops-query CLI 三个 Bug 修复设计

**日期**: 2026-07-03
**分支**: fix/aiops-query-cli-bugfix
**状态**: 设计已确认，待实施

---

## 概述

用户通过 `aiops-rag` skill 写入文档/服务/主机时发现三个 Bug。经代码调查，根因均已定位。本设计描述修复方案，涵盖 CLI 脚本、SKILL.md 文档、以及当前 YAML 数据的修复。

| Bug | 优先级 | 根因 | 修复方向 |
|-----|--------|------|---------|
| Bug 1: write-tech/sop/incident 报 `NameError: _write_cmd` | P0 | `_write_cmd` 函数被调用但从未定义 | 补定义 `_write_cmd` 函数 |
| Bug 2: add-service 误报"host 不存在" | P1 | add-service 在 host 不存在时只警告不阻止，产生悬空引用 | 改为报错退出 + 修复当前 YAML 悬空引用 |
| Bug 3: update-node 拒绝 vip/role/ports 属性 | P2 | 这些属性不属于用户指定的 Label（vip∈Cluster, role∈PART_OF 关系, ports 是独立 Port 节点） | 保持图模型不变，CLI 端做属性校验 + 友好提示 |

**关键事实**：
- `add-host` 和 `add-service` 都读同一个 YAML 文件（`~/.openclaw/workspace-shared/aiops/rag/wiki/topology/call-graph.yml`），数据源一致
- `add-host` 写入逻辑正确（已通过受控复现验证）
- Bug 2 的"稳定复现"真相：用户先跑 `add-service`（host 不存在→警告→service 带悬空引用写入），`add-host` 之后跑，但悬空引用已产生

---

## Bug 1: 补 `_write_cmd` 函数

### 根因

`aiops-query` 脚本 line 591-596 调用 `_write_cmd(sys.argv, write_sop, 3)` / `_write_cmd(sys.argv, write_tech, 2)` / `_write_cmd(sys.argv, write_incident, 2)`，但**全文从未定义**该函数。

`_parse_write_args(argv, svc_pos)`（line 113-136）已存在，负责解析 `--file` 和 `--tags`。`write_sop` / `write_tech` / `write_incident`（line 230-349）也已定义且逻辑完整。缺失的只是把 argv 解析和 write 函数粘合起来的 `_write_cmd` 分发函数。

### 修复

**位置**：`aiops-query` 脚本，`_parse_write_args` 之后（约 line 137）

**新增函数**：
```python
def _write_cmd(argv, fn, svc_pos):
    """分发 write-tech / write-sop / write-incident 命令。

    argv: sys.argv
    fn: write_sop / write_tech / write_incident
    svc_pos: 最后一个位置参数的索引
             write-sop = 3 (cmd, svc_id, sop_type)
             write-tech / write-incident = 2 (cmd, svc_id)
    """
    service_id = argv[2]
    body, tags = _parse_write_args(argv, svc_pos)
    if fn is write_sop:
        sop_type = argv[3]
        write_sop(service_id, sop_type, body, tags=tags)
    else:
        fn(service_id, body, tags=tags)
```

### 设计要点

- 复用现有 `_parse_write_args`，不重写解析逻辑
- `write_sop` 签名是 `(service_id, sop_type, body, tags, host_id)`，比 tech/incident 多一个 `sop_type` 位置参数，故 `svc_pos=3`（sop_type 在 `argv[3]`）；tech/incident 的 `svc_pos=2`
- 不改 `write_sop` / `write_tech` / `write_incident` 三个函数本身（逻辑完整）
- 用户原描述说"调用后端的 write-tech API" —— 实际无此后端 API，write 函数在 CLI 本地写 markdown 到 `wiki/` 目录，再调 `/index-all` 触发 ES 索引。Neo4j 不参与文档写入

### 验证

```bash
./aiops-query write-tech svc_pangu_db --file /tmp/tech_pangu_db.md --tags '技术文档,Pangu,MySQL'
./aiops-query write-sop svc_nginx_company 磁盘满-清理日志 --file /tmp/sop.md --tags '应急,Nginx'
./aiops-query write-incident svc_pangu_db --file /tmp/incident.md --tags '故障,复盘'
```

---

## Bug 2: 阻止悬空引用 + 数据修复

### 根因

`add_service` 函数（line 352-392）在 host 不存在时**只警告不阻止**：
```python
if not any(h["id"] == svc_host for h in data.get("hosts", [])):
    print(f"警告: host '{svc_host}' 不存在于拓扑中，请先 add-host")
    # ← 没有 sys.exit，继续创建 service
```

这会产生**悬空引用**（service.deploys_on 指向不存在的 host）。

**连锁影响**：
1. 悬空引用写入 YAML
2. 下次任何 `/reload-topology`（add-host / add-service / index 都会触发）运行 `load-topology.py`
3. `load-topology.py` 的 `validate_cross_refs` 发现悬空引用 → 校验失败 → 直接 return
4. Neo4j 不更新（停在旧状态），ES 重新索引时也带着错误引用

**注意**：`load-topology.py` 的校验在 `MATCH (n) DETACH DELETE n` 之前，所以校验失败时**不会清空 Neo4j**，但 Neo4j 也无法通过 reload 更新。

### 当前数据状态

YAML 里 `svc_pangu_db.deploys_on = host_pangu_db_master`，但 hosts 列表只有 `host_pangu_db_slave`，没有 `host_pangu_db_master`。每次 `/reload-topology` 都返回：
```
拓扑文件校验失败:
  - svc_pangu_db.deploys_on='host_pangu_db_master' 不存在于 hosts 列表中
```

### 修复

#### 2a. 代码修复（`add_service` 函数，line 364-365）

**原代码**：
```python
if not any(h["id"] == svc_host for h in data.get("hosts", [])):
    print(f"警告: host '{svc_host}' 不存在于拓扑中，请先 add-host")
```

**改为**：
```python
if not any(h["id"] == svc_host for h in data.get("hosts", [])):
    print(f"错误: host '{svc_host}' 不存在于拓扑中，请先 add-host")
    print(f"  提示: ./aiops-query add-host --id {svc_host} --name <名称> --ip <IP> --os 'CentOS 7'")
    sys.exit(1)
```

**设计要点**：
- 从"警告+继续"改成"错误+退出"，从源头杜绝悬空引用
- 补一条提示命令，降低用户认知负担
- 不改 `add_host`（已验证其写入逻辑正确）

#### 2b. 数据修复（当前 YAML 的悬空引用）

把缺失的 `host_pangu_db_master` 补回 YAML `hosts` 列表（值来自用户原始命令）：
```yaml
- id: host_pangu_db_master
  name: dbm1
  ip: 10.33.16.144
  os: CentOS 7
```

**插入位置**：`hosts` 列表末尾（`host_pangu_db_slave` 条目之后）。可直接编辑 `wiki/topology/call-graph.yml`，或用 `add-host` 命令补录（但需先临时移除 `svc_pangu_db` 的悬空引用，否则 `reload-topology` 仍会校验失败）—— 推荐直接编辑 YAML 更稳妥。

**YAML 格式验证**（编辑后必须执行）：
```bash
python3 -c "import yaml; yaml.safe_load(open('wiki/topology/call-graph.yml')); print('YAML 格式正确')"
```

修复后验证：
```bash
curl -X POST http://localhost:8001/api/v1/reload-topology
# 期望: {"status":"ok","output":"... Topology loaded from ..."}
./aiops-query health
# 期望: sync 状态恢复正常
```

#### 2c. 不做的事（YAGNI）

- ❌ 不加 `--allow-dangling` 选项（当前无此需求）
- ❌ 不改 `add_host` 的幂等性（已正常工作）
- ❌ 不加拓扑缓存刷新逻辑（根因不是缓存）

### 验证

```bash
# 用不存在的 host 跑 add-service → 应报错退出
./aiops-query add-service --id svc_test --name test --host host_not_exist --port 8080
# 期望: 错误: host 'host_not_exist' 不存在于拓扑中，请先 add-host

# 数据修复后 reload-topology 应成功
curl -X POST http://localhost:8001/api/v1/reload-topology
# 期望: {"status":"ok",...}
```

---

## Bug 3: CLI 端属性校验 + 友好提示

### 根因

`update_node` 函数（line 474-495）直接把用户给的 key 发 PATCH 给后端。后端 `routes.py:526-548` 调 `update_node(driver, label, key_field, node_id, props)`，该函数用 `app/schema.py` 的 `ALLOWED_PROPS` 白名单校验：

| Label | 允许的属性 |
|-------|-----------|
| Service | `id, name, status, description, aliases` |
| Host | `id, name, ip, os` |
| Cluster | `service_id, name, vip` |
| Port | `number, protocol, status` |
| Document | `id, title, type, updated_at` |
| PART_OF（关系） | `role` |

用户三条命令的属性实际归属：

| 命令 | 实际归属 | 说明 |
|------|---------|------|
| `Service vip` | `vip` 是 **Cluster** 的属性 | 应用 `update-node Cluster <svc_id> vip ...`（Cluster 用 service_id 查询） |
| `Host role` | `role` 是 **PART_OF 关系**的属性 | 不是 Host 节点属性，无法通过 update-node 修改 |
| `Service ports` | `ports` 在 Neo4j 里是独立 **Port** 节点 | 通过 `HAS_PORT` 连到 Host，不是 Service 属性 |

**结论**：白名单本身符合图模型设计，是命令用错了 Label。修复方向是 CLI 端提前校验 + 友好提示，不扩展白名单（避免数据冗余，如 Service.vip 与 Cluster.vip 重复）。

### 修复

**位置**：`aiops-query` 脚本

#### 3a. 新增常量（脚本顶部，靠近 `API` 定义）

```python
_NODE_PROPS = {
    "Service":  {"id", "name", "status", "description", "aliases"},
    "Host":     {"id", "name", "ip", "os"},
    "Port":     {"number", "protocol", "status"},
    "Document": {"id", "title", "type", "updated_at"},
    "Cluster":  {"service_id", "name", "vip"},
}

# 用户常见误用 → 正确归属提示
_PROP_HINTS = {
    "vip":   "'vip' 是 Cluster 的属性。正确: update-node Cluster <svc_id> vip <value>",
    "role":  "'role' 是 PART_OF 关系的属性（host 在集群中的角色），不是 Host 节点属性",
    "ports": "'ports' 在 Neo4j 里是独立 Port 节点（HAS_PORT 连到 Host），不是 Service 属性",
}
```

> **扩展性说明**：`_PROP_HINTS` 目前只包含 `vip`/`role`/`ports` 三个高频误用属性。后续可根据用户反馈补充更多常见误用（如 `status`、`description` 等跨 Label 共有属性的误用场景）。新增条目时同步更新 `SKILL.md` 的"update-node 支持的属性"章节。

#### 3b. `update_node` 改造（PATCH 前加本地校验）

```python
def update_node(label, node_id, key, value):
    if label not in _NODE_PROPS:
        print(f"错误: 未知 Label '{label}'。有效: {list(_NODE_PROPS.keys())}")
        sys.exit(1)
    if key not in _NODE_PROPS[label]:
        hint = _PROP_HINTS.get(key)
        if hint:
            print(f"错误: {hint}")
        else:
            # 找出 key 实际属于哪些 Label（可能多个，如 name 同时属于 Service/Host/Cluster）
            matching_labels = [lbl for lbl, props in _NODE_PROPS.items() if key in props]
            if matching_labels:
                print(f"错误: '{key}' 是 {', '.join(matching_labels)} 的属性，不是 {label} 的。")
                print(f"  试试: aiops-query update-node {matching_labels[0]} <node_id> {key} <value>")
            else:
                print(f"错误: '{key}' 不是 {label} 的有效属性。")
                print(f"  {label} 支持的属性: {sorted(_NODE_PROPS[label])}")
        sys.exit(1)
    # 原有 PATCH 逻辑不变
    import urllib.request, urllib.error
    try:
        typed_value = int(value)
    except ValueError:
        typed_value = value
    payload = json.dumps({key: typed_value}).encode()
    req = urllib.request.Request(
        f"{API}/node/{label}/{node_id}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(json.dumps(json.loads(resp.read()), indent=2, ensure_ascii=False))
    except urllib.error.HTTPError as e:
        print(f"错误: {e.code} — {e.read().decode()[:200]}")
        sys.exit(1)
```

### 设计要点

- 属性表与后端 `app/schema.py` 的 `ALLOWED_PROPS` 保持一致（手动同步，因 CLI 是独立脚本不依赖后端模块）
- `_PROP_HINTS` 只放高频误用的 3 个属性（vip/role/ports），其他走通用"找出正确 Label"逻辑
- 后端 `routes.py` 的校验保留（防御性），CLI 校验只是更早给出友好提示
- 不扩展白名单，不改图模型

### 验证

```bash
./aiops-query update-node Service svc_pangu_gateway vip '10.33.16.177'
# 期望: 错误: 'vip' 是 Cluster 的属性。正确: update-node Cluster <svc_id> vip <value>

./aiops-query update-node Cluster svc_pangu_gateway vip '10.33.16.177'
# 期望: 成功更新（Cluster 用 service_id 查询）

./aiops-query update-node Host host_pangu_mq_01 role 'RabbitMQ+Redis'
# 期望: 错误: 'role' 是 PART_OF 关系的属性...
```

---

## SKILL.md 同步更新

修复 CLI 的同时，`SKILL.md` 需同步更新（两份副本都改）。改动点：

### Bug 2 相关

**line 61**（维护命令表 add-service 行）：补注强制校验
```
| `aiops-query add-service --id <id> --name <名> --host <hid> [--port 8080] [--call svc_x:http:80]` | 新增服务到拓扑（host 不存在时报错退出） | ... |
```

**line 228-237**（拓扑新增规范）：现有规范 line 232 已写"先注册 Host 再注册 Service"，line 233 已写"host 在拓扑中已存在，若不存在先 add-host"。补注一行说明代码已强制：
```
> **强制校验**：`add-service` 已实现 host 存在性强制校验，host 不存在时直接报错退出（不再仅警告）。
```

### Bug 3 相关

**line 63**（维护命令表 update-node 行）之后，新增一节"update-node 各 Label 支持属性"：

```markdown
## update-node 支持的属性

不同 Label 支持的属性不同，用错 Label 会报错并给出提示：

| Label | 支持的属性 | 节点标识字段 |
|-------|-----------|-------------|
| Service | id, name, status, description, aliases | id |
| Host | id, name, ip, os | id |
| Port | number, protocol, status | number |
| Document | id, title, type, updated_at | id |
| Cluster | service_id, name, vip | service_id |

**常见误用提示**：
- `vip` 是 **Cluster** 的属性，不是 Service。正确：`update-node Cluster <svc_id> vip <value>`
- `role` 是 **PART_OF 关系**的属性（host 在集群中的角色），不是 Host 节点属性，无法通过 update-node 修改
- `ports` 在 Neo4j 里是独立 **Port** 节点（通过 `HAS_PORT` 连到 Host），不是 Service 属性
```

### Bug 1 相关

SKILL.md 不需要改。write-sop/write-tech/write-incident 命令文档已存在（line 58-60, 119-138），修复后命令能用，文档描述本身正确。

---

## 文件同步策略

存在两份内容相同的 skill 副本（非 symlink）：

| 路径 | 角色 |
|------|------|
| `~/.openclaw/workspace-shared/aiops/rag/skills/` | git 跟踪的源 |
| `~/.openclaw/skills/aiops-rag/` | OpenClaw 部署目录（运行时实际加载） |

### 本次同步范围

| 文件 | 是否改 | 同步方式 |
|------|--------|---------|
| `aiops-query` | 是（Bug 1/2/3 代码修复） | 改 git 源 → cp 到部署目录 |
| `SKILL.md` | 是（Bug 2/3 文档更新） | 改 git 源 → cp 到部署目录 |
| `templates/*.md` | 否 | 不涉及 |
| `test_queries.json` | 否 | 不涉及 |
| `cron/sync-health-check.sh` | 否 | 不涉及 |

### 同步步骤

1. 在 git 源（`workspace-shared/aiops/rag/skills/`）改 `aiops-query` 和 `SKILL.md`
2. `cp` 到部署目录（`~/.openclaw/skills/aiops-rag/`）
3. `chmod +x` 确保 `aiops-query` 可执行
4. `diff` 验证两份内容一致

### 后续建议（不在本次范围）

把 `~/.openclaw/skills/aiops-rag/aiops-query` 和 `SKILL.md` 改成 symlink 指向 git 源，避免未来再漂移。本次先双写，symlink 单独议。

---

## 测试验证

### Bug 1 验证
```bash
cd ~/.openclaw/skills/aiops-rag
./aiops-query write-tech svc_pangu_db --file /tmp/tech_pangu_db.md --tags '技术文档,Pangu,MySQL'
# 期望: 技术文档写入: <path>

./aiops-query write-sop svc_nginx_company 磁盘满-清理日志 --file /tmp/sop.md --tags '应急,Nginx'
# 期望: SOP 写入: <path>

./aiops-query write-incident svc_pangu_db --file /tmp/incident.md --tags '故障,复盘'
# 期望: 故障记录写入: <path>
```

### Bug 2 验证
```bash
# 代码：host 不存在应报错退出
./aiops-query add-service --id svc_test --name test --host host_not_exist --port 8080
# 期望: 错误: host 'host_not_exist' 不存在于拓扑中，请先 add-host

# 数据：reload-topology 应成功
curl -X POST http://localhost:8001/api/v1/reload-topology
# 期望: {"status":"ok",...}
```

### Bug 3 验证
```bash
./aiops-query update-node Service svc_pangu_gateway vip '10.33.16.177'
# 期望: 错误: 'vip' 是 Cluster 的属性...

./aiops-query update-node Cluster svc_pangu_gateway vip '10.33.16.177'
# 期望: 成功更新

./aiops-query update-node Host host_pangu_mq_01 role 'RabbitMQ+Redis'
# 期望: 错误: 'role' 是 PART_OF 关系的属性...
```

### 回归验证
- `./aiops-query query 'nginx 502 排查'` — 知识库问答不受影响
- `./aiops-query topology svc_nginx_company` — 拓扑查询不受影响
- `./aiops-query health` — 健康检查恢复正常（数据修复后）

---

## 回滚方案

修复后若出现问题，按以下顺序回滚：

1. **代码回滚**：`git revert <commit-hash>` 撤销对应 commit（CLI 脚本 / SKILL.md 各自独立 revert）
2. **数据回滚**：从 git 恢复 `call-graph.yml`
   ```bash
   git checkout HEAD~1 -- rag/wiki/topology/call-graph.yml
   curl -X POST http://localhost:8001/api/v1/reload-topology
   ```
   注意：数据回滚会重新引入悬空引用（`svc_pangu_db` → `host_pangu_db_master`），`/reload-topology` 会再次校验失败 —— 这是回滚到修复前状态，可接受。
3. **部署回滚**：从 git 源重新 `cp` 到部署目录
   ```bash
   cp rag/skills/aiops-query ~/.openclaw/skills/aiops-rag/aiops-query
   cp rag/skills/SKILL.md ~/.openclaw/skills/aiops-rag/SKILL.md
   chmod +x ~/.openclaw/skills/aiops-rag/aiops-query
   ```
4. **验证回滚成功**：跑一次 `./aiops-query health` 确认服务状态

## 监控指标

修复上线后观察以下指标（持续 1-2 周）：

| 指标 | 采集方式 | 期望值 |
|------|---------|--------|
| `add-service` 报错退出次数 | 人工观察 / 日志 | > 0（说明用户尝试创建悬空引用被拦截，符合预期） |
| `update-node` CLI 端报错次数 | 人工观察 | 减少（友好提示让用户改用正确 Label） |
| `/reload-topology` 成功率 | `curl` + 检查返回 | 恢复 100%（数据修复后校验通过） |
| Neo4j 数据一致性 | `./aiops-query health` 的 sync 字段 | 无 orphan_docs / dangling_doc_refs |
| `write-tech`/`write-sop`/`write-incident` 成功率 | 人工执行验证命令 | 100%（Bug 1 修复后） |

若 `/reload-topology` 仍失败，说明 YAML 还有其他悬空引用未修复，需排查 `validate_cross_refs` 报错。

## 用户通知

修复合并后通知用户：

1. **SKILL.md 更新日志**：在 `SKILL.md` 末尾新增"变更记录"章节（若不存在），记录：
   - `add-service` 现在强制校验 host 存在性（行为变更）
   - `update-node` 新增属性校验和友好提示
   - `write-tech`/`write-sop`/`write-incident` 修复
2. **团队通知**：在团队群说明三个 Bug 已修复，命令用法基本不变，唯一行为变化是 `add-service` 在 host 不存在时报错退出（之前是警告）。

---

## 不做的事（YAGNI）

- ❌ 不改后端 `app/` 代码（routes.py / schema.py / graph_retriever.py）—— 三个 Bug 都在 CLI 层
- ❌ 不扩展 `ALLOWED_PROPS` 白名单（避免图模型冗余）
- ❌ 不加 `--allow-dangling` 选项
- ❌ 不改 `add_host` 幂等性
- ❌ 不新增 pytest 测试（CLI 脚本目前无测试覆盖，本次不补，保持范围聚焦）
- ❌ 不把 skill 副本改 symlink（单独议）

---

## 提交策略

- 特性分支 `fix/aiops-query-cli-bugfix`（遵循父级 CLAUDE.md 的 PR 规则，不直推 main）
- 提交顺序：
  1. 设计文档（本文件）
  2. CLI 脚本修复（aiops-query）
  3. SKILL.md 更新
  4. YAML 数据修复（补 host_pangu_db_master）
  5. 部署目录同步
- PR 合并到 main

## 影响范围

- 只改 CLI 脚本 + SKILL.md + YAML 数据，不动后端 `app/` 代码
- 不影响 `/query`、`/topology`、`/impact` 等核心 API
- 数据修复（补 `host_pangu_db_master`）会让 `/reload-topology` 恢复正常，Neo4j 重新可更新
