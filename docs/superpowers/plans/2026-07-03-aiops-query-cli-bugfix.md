# aiops-query CLI Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three bugs in the aiops-query CLI (write-tech NameError, add-service dangling references, update-node property rejection) plus repair current YAML data damage and sync two skill copies.

**Architecture:** All code fixes are in the CLI script (`rag/skills/aiops-query`) — no backend `app/` changes. Add a `_write_cmd` dispatcher function, harden `add_service` to error-exit on missing host, add local property validation with friendly hints to `update_node`. Update `SKILL.md` to document behavior changes. Repair YAML by adding the missing `host_pangu_db_master` host. Finally sync the git source to the deployment copy.

**Tech Stack:** Python 3 stdlib (urllib, json, ast) + PyYAML; bash for sync/verification. No new dependencies.

## Global Constraints

- CLI script uses only Python 3 stdlib + PyYAML — no new deps
- Two skill copies must stay in sync: `rag/skills/` (git source) and `~/.openclaw/skills/aiops-rag/` (deployment)
- No backend `app/` code changes (routes.py / schema.py / graph_retriever.py untouched)
- No new pytest tests — CLI script has no test coverage currently; verification is manual (per spec YAGNI)
- Commit format: `fix:` / `docs:` with Co-Authored-By trailers for Claude and Happy
- Feature branch: `fix/aiops-query-cli-bugfix` (already created, design doc already committed)
- `aiops-query` must remain executable (`chmod +x`) after any sync
- RAG API must be running (`docker ps` shows `rag-api` Up) for functional verification of Tasks 2/3/5

## File Structure

| File | Responsibility | Touched by Task |
|------|---------------|-----------------|
| `rag/skills/aiops-query` | CLI script — all three bug fixes | 1, 2, 3 |
| `rag/skills/SKILL.md` | Skill docs — behavior changes + property table | 4 |
| `rag/wiki/topology/call-graph.yml` | Topology data — add missing host | 5 |
| `~/.openclaw/skills/aiops-rag/aiops-query` | Deployment copy of CLI | 6 (sync only) |
| `~/.openclaw/skills/aiops-rag/SKILL.md` | Deployment copy of skill docs | 6 (sync only) |

**Design doc**: `docs/superpowers/specs/2026-07-03-aiops-query-cli-bugfix-design.md` (already committed, reference for rationale)

---

### Task 1: Bug 1 — Add `_write_cmd` dispatcher function

**Files:**
- Modify: `rag/skills/aiops-query` — insert new function between `_parse_write_args` (ends line 136) and `_index` (line 139)

**Interfaces:**
- Consumes: `_parse_write_args(argv, svc_pos)` (line 113, returns `(body, tags)` tuple); `write_sop` / `write_tech` / `write_incident` (defined at lines 230/269/297)
- Produces: `_write_cmd(argv, fn, svc_pos)` — called by dispatch block at lines 592/594/596. `fn` is one of `write_sop`/`write_tech`/`write_incident`. `svc_pos` is 3 for write-sop (has extra `sop_type` positional arg), 2 for write-tech/write-incident.

- [ ] **Step 1: Confirm insertion point**

Run:
```bash
grep -n "^def _parse_write_args\|^def _index\b" rag/skills/aiops-query
```
Expected: `_parse_write_args` at line 113, `_index` at line 139. The new function goes in the blank lines between them (lines 137-138).

- [ ] **Step 2: Insert `_write_cmd` function**

Using a Python script for precise insertion (avoids sed multi-line issues). Create `/tmp/insert_write_cmd.py`:

```python
import io
path = 'rag/skills/aiops-query'
lines = open(path, encoding='utf-8').readlines()
# Find the line "def _index(full=False):" and insert before it
insert_before = None
for i, line in enumerate(lines):
    if line.startswith('def _index(full=False):'):
        insert_before = i
        break
assert insert_before is not None, "def _index not found"
new_func = '''
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


'''
lines.insert(insert_before, new_func)
open(path, 'w', encoding='utf-8').writelines(lines)
print("Inserted _write_cmd before def _index")
```

Run:
```bash
python3 /tmp/insert_write_cmd.py
```
Expected output: `Inserted _write_cmd before def _index`

- [ ] **Step 3: Static check — function is defined and syntactically valid**

Run:
```bash
python3 -m py_compile rag/skills/aiops-query && echo "syntax OK"
python3 -c "
import ast
tree = ast.parse(open('rag/skills/aiops-query').read())
funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
assert '_write_cmd' in funcs, '_write_cmd not found'
assert '_parse_write_args' in funcs, '_parse_write_args not found'
print('OK: _write_cmd defined')
"
```
Expected: `syntax OK` then `OK: _write_cmd defined`

- [ ] **Step 4: Functional check — write-tech no longer raises NameError**

Create a temp test file:
```bash
echo "# 测试技术文档" > /tmp/test_writecmd.md
```

Run (using git source directly, `svc_test_writecmd` is a throwaway id not in topology):
```bash
./rag/skills/aiops-query write-tech svc_test_writecmd --file /tmp/test_writecmd.md --tags 'test'
```
Expected output: `技术文档写入: /root/.openclaw/workspace-shared/aiops/rag/wiki/services/svc_test_writecmd-svc_test_writecmd/tech-arch.md`

If you see `NameError: name '_write_cmd' is not defined`, the fix failed — re-check Step 2.

- [ ] **Step 5: Clean up test artifacts**

```bash
rm -rf rag/wiki/services/svc_test_writecmd-svc_test_writecmd
rm -f /tmp/test_writecmd.md
```

- [ ] **Step 6: Commit**

```bash
git add rag/skills/aiops-query
git commit -m "$(cat <<'MSG'
fix: add _write_cmd dispatcher to fix write-tech/sop/incident NameError

write-tech/write-sop/write-incident commands called _write_cmd() which was
never defined. Add the dispatcher between _parse_write_args and _index,
reusing existing _parse_write_args for --file/--tags parsing.

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>
MSG
)"
```

---

### Task 2: Bug 2a — `add_service` error-exit on missing host

**Files:**
- Modify: `rag/skills/aiops-query:364-365` — replace 2-line warning with 3-line error+exit

**Interfaces:**
- Consumes: `args` dict (passed to `add_service`), `sys.exit` (stdlib)
- Produces: `add_service` now exits with code 1 when `--host` references a non-existent host, instead of warning and continuing. Downstream effect: no more dangling `deploys_on` references in YAML.

- [ ] **Step 1: Confirm the exact lines to replace**

Run:
```bash
sed -n '364,365p' rag/skills/aiops-query
```
Expected:
```
    if not any(h["id"] == svc_host for h in data.get("hosts", [])):
        print(f"警告: host '{svc_host}' 不存在于拓扑中，请先 add-host")
```

- [ ] **Step 2: Replace warning with error+exit**

Create `/tmp/fix_add_service.py`:

```python
path = 'rag/skills/aiops-query'
content = open(path, encoding='utf-8').read()
old = '''    if not any(h["id"] == svc_host for h in data.get("hosts", [])):
        print(f"警告: host '{svc_host}' 不存在于拓扑中，请先 add-host")'''
new = '''    if not any(h["id"] == svc_host for h in data.get("hosts", [])):
        print(f"错误: host '{svc_host}' 不存在于拓扑中，请先 add-host")
        print(f"  提示: ./aiops-query add-host --id {svc_host} --name <名称> --ip <IP> --os 'CentOS 7'")
        sys.exit(1)'''
assert old in content, "old block not found — line numbers may have shifted"
content = content.replace(old, new)
open(path, 'w', encoding='utf-8').write(content)
print("Replaced warning with error+exit")
```

Run:
```bash
python3 /tmp/fix_add_service.py
```
Expected: `Replaced warning with error+exit`

- [ ] **Step 3: Static check — syntax valid**

```bash
python3 -m py_compile rag/skills/aiops-query && echo "syntax OK"
```
Expected: `syntax OK`

- [ ] **Step 4: Functional check — add-service with missing host exits non-zero**

Run:
```bash
./rag/skills/aiops-query add-service --id svc_test_dangling --name test --host host_not_exist --port 8080; echo "exit_code=$?"
```
Expected output (two lines):
```
错误: host 'host_not_exist' 不存在于拓扑中，请先 add-host
  提示: ./aiops-query add-host --id host_not_exist --name <名称> --ip <IP> --os 'CentOS 7'
exit_code=1
```

If `exit_code=0` or you see `服务已添加`, the fix failed.

- [ ] **Step 5: Verify no side effects (service NOT created)**

```bash
python3 -c "
import yaml
d = yaml.safe_load(open('rag/wiki/topology/call-graph.yml'))
svcs = [s['id'] for s in d.get('services', []) if s['id'] == 'svc_test_dangling']
assert not svcs, 'svc_test_dangling should NOT be in YAML'
print('OK: no dangling service created')
"
```
Expected: `OK: no dangling service created`

- [ ] **Step 6: Commit**

```bash
git add rag/skills/aiops-query
git commit -m "$(cat <<'MSG'
fix: add-service error-exits on missing host instead of warning

Previously add-service only warned when --host referenced a non-existent
host, then created the service anyway — producing dangling deploys_on
references that broke validate_cross_refs and blocked /reload-topology.
Now exits 1 with a hint showing the correct add-host command.

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>
MSG
)"
```

---

### Task 3: Bug 3 — Add property validation to `update_node`

**Files:**
- Modify: `rag/skills/aiops-query` — add `_NODE_PROPS`/`_PROP_HINTS` constants after line 41 (`API = ...`); replace entire `update_node` function (lines 474-495 after Task 1/2 shifts — locate by `def update_node`)

**Interfaces:**
- Consumes: `_NODE_PROPS` and `_PROP_HINTS` module-level constants (defined in this task)
- Produces: `update_node(label, node_id, key, value)` now validates `label` and `key` locally before PATCH. Exits 1 with a friendly hint if invalid. Valid requests still PATCH to `/node/{label}/{node_id}` as before.

- [ ] **Step 1: Add `_NODE_PROPS` and `_PROP_HINTS` constants**

Create `/tmp/add_constants.py`:

```python
path = 'rag/skills/aiops-query'
content = open(path, encoding='utf-8').read()
anchor = 'API = "http://localhost:8001/api/v1"\n'
assert anchor in content, "API anchor not found"
constants = '''

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
'''
content = content.replace(anchor, anchor + constants, 1)
open(path, 'w', encoding='utf-8').write(content)
print("Added _NODE_PROPS and _PROP_HINTS")
```

Run:
```bash
python3 /tmp/add_constants.py
```
Expected: `Added _NODE_PROPS and _PROP_HINTS`

- [ ] **Step 2: Replace `update_node` function with validation-aware version**

Create `/tmp/replace_update_node.py`:

```python
import re
path = 'rag/skills/aiops-query'
content = open(path, encoding='utf-8').read()

# Match the full update_node function (from def line to next def or blank-line+def)
old_pattern = r'def update_node\(label: str, node_id: str, key: str, value: str\):.*?\n\n\ndef index'
old_match = re.search(old_pattern, content, re.DOTALL)
assert old_match, "update_node function not found"
old_func = old_match.group(0)

new_func = '''def update_node(label: str, node_id: str, key: str, value: str):
    """Update any node property via PATCH /node/{label}/{id}.
    Labels: Service, Host, Port, Document, Cluster."""
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
    import urllib.request, urllib.error
    # Auto-convert numeric values
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


def index'''

content = content.replace(old_func, new_func)
open(path, 'w', encoding='utf-8').write(content)
print("Replaced update_node with validation-aware version")
```

Run:
```bash
python3 /tmp/replace_update_node.py
```
Expected: `Replaced update_node with validation-aware version`

- [ ] **Step 3: Static check — syntax valid, constants defined**

```bash
python3 -m py_compile rag/skills/aiops-query && echo "syntax OK"
python3 -c "
import ast
tree = ast.parse(open('rag/skills/aiops-query').read())
assigns = [t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)]
assert '_NODE_PROPS' in assigns, '_NODE_PROPS not found'
assert '_PROP_HINTS' in assigns, '_PROP_HINTS not found'
print('OK: constants defined')
"
```
Expected: `syntax OK` then `OK: constants defined`

- [ ] **Step 4: Functional check — vip on Service gives Cluster hint**

```bash
./rag/skills/aiops-query update-node Service svc_pangu_gateway vip '10.33.16.177'; echo "exit=$?"
```
Expected:
```
错误: 'vip' 是 Cluster 的属性。正确: update-node Cluster <svc_id> vip <value>
exit=1
```

- [ ] **Step 5: Functional check — role on Host gives PART_OF hint**

```bash
./rag/skills/aiops-query update-node Host host_pangu_mq_01 role 'RabbitMQ'; echo "exit=$?"
```
Expected:
```
错误: 'role' 是 PART_OF 关系的属性（host 在集群中的角色），不是 Host 节点属性
exit=1
```

- [ ] **Step 6: Functional check — ports on Service gives Port hint**

```bash
./rag/skills/aiops-query update-node Service svc_pangu_mq ports '[2379]'; echo "exit=$?"
```
Expected:
```
错误: 'ports' 在 Neo4j 里是独立 Port 节点（HAS_PORT 连到 Host），不是 Service 属性
exit=1
```

- [ ] **Step 7: Functional check — unknown Label rejected**

```bash
./rag/skills/aiops-query update-node Foo bar baz qux; echo "exit=$?"
```
Expected:
```
错误: 未知 Label 'Foo'。有效: ['Service', 'Host', 'Port', 'Document', 'Cluster']
exit=1
```

- [ ] **Step 8: Functional check — valid update still works (Cluster vip)**

```bash
./rag/skills/aiops-query update-node Cluster svc_pangu_gateway vip '10.33.16.177'
```
Expected: a JSON response (success or 404 if the cluster node doesn't exist in Neo4j — either way, NOT a property validation error). The key point: no `错误:` prefix from local validation.

- [ ] **Step 9: Commit**

```bash
git add rag/skills/aiops-query
git commit -m "$(cat <<'MSG'
fix: add local property validation to update-node with friendly hints

update-node now validates label and key against _NODE_PROPS whitelist
before PATCHing. Common misuses (vip on Service, role on Host, ports on
Service) get targeted hints pointing to the correct Label. Unknown labels
and keys are rejected with the list of valid options. Backend whitelist
in schema.py unchanged — this is a CLI-side UX improvement only.

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>
MSG
)"
```

---

### Task 4: Update SKILL.md with behavior changes and property table

**Files:**
- Modify: `rag/skills/SKILL.md` — line 61 (add-service row), after line 63 (new property table section), line 233 area (enforcement note)

**Interfaces:**
- Consumes: property names from `_NODE_PROPS` (Task 3)
- Produces: documentation matching the new CLI behavior. SKILL.md is loaded into agent system prompt, so accuracy matters.

- [ ] **Step 1: Update add-service row (line 61) to note enforcement**

Create `/tmp/update_skill.py`:

```python
path = 'rag/skills/SKILL.md'
content = open(path, encoding='utf-8').read()

# Change 1: add-service row — add "(host 不存在时报错退出)"
old1 = '| `aiops-query add-service --id <id> --name <名> --host <hid> [--port 8080] [--call svc_x:http:80]` | 新增服务到拓扑 |'
new1 = '| `aiops-query add-service --id <id> --name <名> --host <hid> [--port 8080] [--call svc_x:http:80]` | 新增服务到拓扑（host 不存在时报错退出） |'
assert old1 in content, "add-service row not found"
content = content.replace(old1, new1)

# Change 2: insert property table section after the update-node row (line 63)
# The update-node row ends with the example containing "Ubuntu 22.04"
old2 = "| `aiops-query update-node <Label> <node_id> <key> <value>` | 更新任意节点属性 | `aiops-query update-node Host host_nginx_01 os 'Ubuntu 22.04'` |\n"
new2 = old2 + """
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
"""
assert old2 in content, "update-node row not found"
content = content.replace(old2, new2)

# Change 3: add enforcement note in 拓扑新增规范 (after line 233 "先注册 Host 再注册 Service")
old3 = "2. **先注册 Host 再注册 Service** — 调用 `add-host` 后再 `add-service`，禁止创建引用不存在 host 的 service"
new3 = old3 + "\n   > **强制校验**：`add-service` 已实现 host 存在性强制校验，host 不存在时直接报错退出（不再仅警告）。"
assert old3 in content, "拓扑新增规范 line not found"
content = content.replace(old3, new3)

open(path, 'w', encoding='utf-8').write(content)
print("SKILL.md updated: 3 changes applied")
```

Run:
```bash
python3 /tmp/update_skill.py
```
Expected: `SKILL.md updated: 3 changes applied`

- [ ] **Step 2: Verify all three changes landed**

```bash
echo "--- add-service row ---"
grep -n "新增服务到拓扑（host" rag/skills/SKILL.md
echo "--- property table section ---"
grep -n "## update-node 支持的属性" rag/skills/SKILL.md
echo "--- enforcement note ---"
grep -n "强制校验" rag/skills/SKILL.md
```
Expected: three grep hits, one per section.

- [ ] **Step 3: Commit**

```bash
git add rag/skills/SKILL.md
git commit -m "$(cat <<'MSG'
docs: update SKILL.md for add-service enforcement and update-node properties

- add-service row notes host-existence enforcement (error exit, not warn)
- new section "update-node 支持的属性" with per-Label property table
- 拓扑新增规范 gets a 强制校验 note tying the rule to the code behavior

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>
MSG
)"
```

---

### Task 5: Bug 2b — Repair YAML data (add missing `host_pangu_db_master`)

**Files:**
- Modify: `rag/wiki/topology/call-graph.yml` — add one entry to the `hosts:` list, after `host_pangu_db_slave` (line 633)

**Interfaces:**
- Consumes: the `hosts:` list in the YAML (line 503 onwards)
- Produces: a YAML that passes `validate_cross_refs` — `/reload-topology` will succeed and Neo4j becomes updateable again.

- [ ] **Step 1: Confirm the current dangling reference**

```bash
curl -s -X POST http://localhost:8001/api/v1/reload-topology
```
Expected (proof of damage): `{"status":"error","detail":"拓扑文件校验失败:\n  - svc_pangu_db.deploys_on='host_pangu_db_master' 不存在于 hosts 列表中"}` or similar output containing `校验失败`.

- [ ] **Step 2: Add `host_pangu_db_master` to the hosts list**

Create `/tmp/fix_yaml.py`:

```python
path = 'rag/wiki/topology/call-graph.yml'
content = open(path, encoding='utf-8').read()

# The last host entry is host_pangu_db_slave — append master after it
anchor = """- id: host_pangu_db_slave
  name: dbm1-slave
  ip: 10.33.16.140
  os: CentOS 7"""
assert anchor in content, "host_pangu_db_slave anchor not found"
new_entry = anchor + """
- id: host_pangu_db_master
  name: dbm1
  ip: 10.33.16.144
  os: CentOS 7"""
content = content.replace(anchor, new_entry)
open(path, 'w', encoding='utf-8').write(content)
print("Added host_pangu_db_master to hosts list")
```

Run:
```bash
python3 /tmp/fix_yaml.py
```
Expected: `Added host_pangu_db_master to hosts list`

- [ ] **Step 3: Verify YAML format is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('rag/wiki/topology/call-graph.yml')); print('YAML 格式正确')"
```
Expected: `YAML 格式正确`

- [ ] **Step 4: Verify reload-topology now succeeds**

```bash
curl -s -X POST http://localhost:8001/api/v1/reload-topology
```
Expected: `{"status":"ok","output":"... Topology loaded from ..."}` — no `校验失败` in the response.

- [ ] **Step 5: Verify Neo4j has the new host**

```bash
docker exec rag-neo4j cypher-shell -u neo4j -p rag-password "MATCH (h:Host {id: 'host_pangu_db_master'}) RETURN h.id, h.ip"
```
Expected: a row showing `host_pangu_db_master` and `10.33.16.144`.

- [ ] **Step 6: Verify health check sync status**

```bash
./rag/skills/aiops-query health
```
Expected: JSON with `"status": "ok"` or `"degraded"` but no `校验失败`-style errors. The `sync` block should be present.

- [ ] **Step 7: Commit**

```bash
git add rag/wiki/topology/call-graph.yml
git commit -m "$(cat <<'MSG'
fix: add missing host_pangu_db_master to repair dangling deploys_on ref

svc_pangu_db.deploys_on pointed to host_pangu_db_master but the host was
never in the hosts list, so validate_cross_refs failed on every
/reload-topology and Neo4j could not be updated. Add the host entry
(10.33.16.144, CentOS 7) — values from the user's original add-host command.

Generated with [Claude Code](https://claude.ai/code)
via [Happy](https://happy.engineering)

Co-Authored-By: Claude <noreply@anthropic.com>
Co-Authored-By: Happy <yesreply@happy.engineering>
MSG
)"
```

---

### Task 6: Sync to deployment directory and final verification

**Files:**
- Sync: `rag/skills/aiops-query` → `~/.openclaw/skills/aiops-rag/aiops-query`
- Sync: `rag/skills/SKILL.md` → `~/.openclaw/skills/aiops-rag/SKILL.md`

**Interfaces:**
- Consumes: the final git-source versions of `aiops-query` and `SKILL.md` (Tasks 1-4)
- Produces: deployment copies matching git source. OpenClaw agents load from `~/.openclaw/skills/aiops-rag/`, so this is what makes the fix live.

- [ ] **Step 1: Copy git source to deployment directory**

```bash
cp rag/skills/aiops-query ~/.openclaw/skills/aiops-rag/aiops-query
cp rag/skills/SKILL.md ~/.openclaw/skills/aiops-rag/SKILL.md
chmod +x ~/.openclaw/skills/aiops-rag/aiops-query
echo "synced + chmod"
```
Expected: `synced + chmod`

- [ ] **Step 2: Verify the two copies are identical**

```bash
diff rag/skills/aiops-query ~/.openclaw/skills/aiops-rag/aiops-query && echo "aiops-query: identical"
diff rag/skills/SKILL.md ~/.openclaw/skills/aiops-rag/SKILL.md && echo "SKILL.md: identical"
ls -l ~/.openclaw/skills/aiops-rag/aiops-query | awk '{print $1, $NF}'
```
Expected: `aiops-query: identical`, `SKILL.md: identical`, and the perms line starting with `-rwx` (executable).

- [ ] **Step 3: Final regression — Bug 1 (write-tech works)**

```bash
echo "# 回归测试" > /tmp/regress.md
~/.openclaw/skills/aiops-rag/aiops-query write-tech svc_test_regression --file /tmp/regress.md --tags 'test'
```
Expected: `技术文档写入: .../svc_test_regression-svc_test_regression/tech-arch.md` (no NameError).

Cleanup:
```bash
rm -rf rag/wiki/services/svc_test_regression-svc_test_regression /tmp/regress.md
```

- [ ] **Step 4: Final regression — Bug 2 (add-service blocks dangling)**

```bash
~/.openclaw/skills/aiops-rag/aiops-query add-service --id svc_test_reg --name test --host host_nope --port 8080; echo "exit=$?"
```
Expected: `错误: host 'host_nope'...` and `exit=1`.

- [ ] **Step 5: Final regression — Bug 3 (update-node gives hints)**

```bash
~/.openclaw/skills/aiops-rag/aiops-query update-node Service svc_test vip '1.2.3.4'; echo "exit=$?"
```
Expected: `错误: 'vip' 是 Cluster 的属性...` and `exit=1`.

- [ ] **Step 6: Final regression — core query still works**

```bash
~/.openclaw/skills/aiops-rag/aiops-query health
```
Expected: JSON with `"status": "ok"` or `"degraded"` (both acceptable — the point is no crash and no `校验失败`).

- [ ] **Step 7: Push the feature branch and create PR**

```bash
git push -u origin fix/aiops-query-cli-bugfix
```
Then create a PR titled "fix: aiops-query CLI bug fixes (write-tech, add-service, update-node)" with:
- Summary of the three bugs and fixes
- Note that YAML data repair is included
- Note that deployment copies are synced

Per project rules: do NOT merge to main directly — PR review required.

---

## Self-Review Notes

**Spec coverage check:**
- Bug 1 (`_write_cmd` undefined) → Task 1 ✓
- Bug 2a (add-service error exit) → Task 2 ✓
- Bug 2b (YAML data repair) → Task 5 ✓
- Bug 3 (update-node validation + hints) → Task 3 ✓
- SKILL.md updates (Bug 2 enforcement note, Bug 3 property table) → Task 4 ✓
- File sync (two copies) → Task 6 ✓
- Rollback / monitoring / notification (spec sections) → these are operational, referenced in spec; no code task needed ✓

**Type/name consistency:**
- `_write_cmd(argv, fn, svc_pos)` — defined Task 1, called at lines 592/594/596 (unchanged) ✓
- `_NODE_PROPS` / `_PROP_HINTS` — defined Task 3, used in `update_node` Task 3 ✓
- `matching_labels` — used only in Task 3's `update_node` ✓
- `host_pangu_db_master` — referenced in Task 5 YAML, matches `svc_pangu_db.deploys_on` ✓

**No placeholders:** every step has exact code or exact commands with expected output. No "TODO" / "implement later" / "similar to Task N".
