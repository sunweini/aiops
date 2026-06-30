# AIOps 前端二期设计规格书

**日期：** 2026-06-30
**分支：** feat/frontend-phase2
**状态：** Draft

---

## 视觉设计

**所有 UI 视觉决策以 `DESIGN.md` 为准。** 本 spec 只描述功能和交互，不重复设计规范。

开发前必须阅读 `DESIGN.md`，关键规范：
- **配色：** 深蓝灰底 `#0a0e1a`，去饱和状态色（红 #F2495C / 黄 #FADE2A / 绿 #73BF69 / 蓝 #5794F2）
- **字体：** Instrument Sans（标题）/ DM Sans（正文）/ Geist Mono（数据）
- **布局：** 左侧栏 200px + 顶部栏 48px + 主内容区
- **间距：** 8px 基准，comfortable 密度
- **动效：** 故障脉动 2s、传播粒子流 1s、受影响节点光晕
- **状态标识：** 永远不单独用颜色 — 必须组合：颜色 + 图标 + 文字标签

---

## 1. 产品定位

AIOps 运维监控平台前端 — 面向运维团队的实时监控 + 知识库一体化平台。

**核心记忆点：** 专业运维工具，故障一目了然。

**双模式：**
- **看板模式（/dashboard）** — 实时拓扑图 + KPI + 告警，可投屏到大屏
- **工作台模式（/workspace）** — 对话查询 RAG 知识库

---

## 2. 技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 框架 | Vue 3 + Composition API | 国内社区活跃，上手快 |
| 构建 | Vite | 快速 HMR，现代工具链 |
| 拓扑可视化 | Cytoscape.js | 图论原生，适合服务拓扑 + 故障传播 |
| UI 组件库 | Naive UI | Vue 3 原生，深色主题支持好 |
| 路由 | Vue Router 4 | SPA 路由 |
| 状态管理 | Pinia | Vue 3 官方推荐 |
| HTTP | Axios | 拦截器/重试/取消请求 |
| 样式 | UnoCSS 或 Tailwind CSS | 原子化 CSS，快速开发 |

---

## 3. 页面路由

```
/                    → 重定向到 /dashboard
/login               → 登录页
/dashboard           → 全局看板（实时拓扑 + KPI + 告警）
/workspace           → 工作台（对话查询）
/workspace/:id       → 对话详情（保留历史）
/hosts               → 主机列表（所有主机状态矩阵）
/hosts/:host_id      → 主机详情（实时指标 + 关联服务）
/services            → 服务列表
/services/:service_id → 服务详情（拓扑 + 部署主机 + 文档）
/alerts              → 告警中心（历史告警 + 统计）
/settings            → 系统设置（阈值配置等）
/settings/users      → 用户管理（admin）
```

---

## 4. 看板页（/dashboard）

### 4.1 布局

```
┌──────────────────────────────────────────────────────┐
│  顶部栏 (48px) — Logo + 搜索 + 时间范围 + 用户     │
├────────┬─────────────────────────────────────────────┤
│ 左侧栏 │  KPI 卡片行 (4 列)                         │
│ (200px)│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│        │ │正常  │ │活跃  │ │受影响│ │MTTD  │       │
│ 导航   │ │28/30 │ │  3   │ │  2   │ │ 4.2m │       │
│        │ └──────┘ └──────┘ └──────┘ └──────┘       │
│        │                                            │
│        │  ┌──────────────────────┐ ┌──────────────┐ │
│        │  │                      │ │ 告警时间线    │ │
│        │  │  服务拓扑图          │ │              │ │
│        │  │  (Cytoscape.js)      │ │ ● ES 集群异常│ │
│        │  │  故障传播可视化      │ │ ● Kibana超时 │ │
│        │  │                      │ │ ● Logstash延迟│ │
│        │  └──────────────────────┘ └──────────────┘ │
└────────┴─────────────────────────────────────────────┘
```

### 4.2 KPI 卡片

| 卡片 | 数据源 | 刷新 | 颜色规则 |
|------|--------|------|----------|
| 正常主机 | `/api/v1/hosts/status` (新) | 60s | 全正常=绿，有异常=红 |
| 活跃告警 | `/api/v1/alerts/active` (新) | 60s | 0=绿，1-2=黄，>2=红 |
| 受影响服务 | 从拓扑图计算 | 60s | 0=绿，>0=黄 |
| 平均发现时间 | 告警时间戳差值 | 实时 | <5m=绿，5-15m=黄，>15m=红 |

### 4.3 服务拓扑图

**渲染引擎：** Cytoscape.js

**数据来源：**
- 拓扑结构：`GET /api/v1/topology?service_id=all` (需新增 `all` 参数)
- 主机状态：`GET /api/v1/hosts/status` (新接口)

**节点样式：**
- 形状：圆形，直径按影响分数缩放
- 颜色：跟随主机状态（healthy/warning/critical/unknown）
- 标签：服务名 + 主机数
- 故障节点：脉动动画（`pulse 2s infinite`）
- 受影响节点：红色光晕（`box-shadow`）

**边样式：**
- 颜色：正常=灰色，故障传播=红色
- 故障路径：粒子流动动画（`flow 1s linear infinite`）
- 线宽：按流量/重要性缩放

**交互：**
- 点击节点 → 右侧抽屉显示详情（主机列表、指标、关联文档）
- 双击节点 → 展开该服务的子拓扑
- 右键节点 → 快捷操作（查看告警、查看文档、模拟故障）
- 缩放/拖拽 → 自由浏览
- 框选 → 批量操作

**布局算法：**
- 默认：`cose`（compound spring embedding）— 力导向
- 可切换：`grid` / `circle` / `breadthfirst`（分层）

### 4.4 告警时间线

**数据源：** `GET /api/v1/alerts/active`

**分组规则：** 按问题分组（同一根因产生的多条告警合并为一个 Problem）

**每条告警显示：**
- 严重级别 badge（critical/warning/info）
- 问题标题
- 影响服务数
- 时间（相对时间：5 分钟前）
- 展开后显示：具体告警列表 + 根因分析

---

## 5. 工作台页（/workspace）

### 5.1 布局

```
┌──────────────────────────────────────────────────────┐
│  顶部栏                                              │
├────────┬─────────────────────────────────────────────┤
│ 对话    │  主内容区                                    │
│ 历史    │  ┌────────────────────────────────────────┐ │
│ (侧栏)  │  │ 欢迎使用 AIOps 知识库                   │ │
│        │  │ 你可以问我：                              │ │
│ 昨天的  │  │ • nginx 502 怎么排查？                    │ │
│ 对话    │  │ • host_es_master_01 影响什么服务？        │ │
│        │  │ • K3s 集群的 SOP 是什么？                  │ │
│ 今天    │  │                                          │ │
│ 的对话  │  │                                          │ │
│        │  │                                          │ │
│        │  └────────────────────────────────────────┘ │
│        │  ┌────────────────────────────────────────┐ │
│        │  │ 输入你的问题...                    [发送] │ │
│        │  └────────────────────────────────────────┘ │
└────────┴─────────────────────────────────────────────┘
```

### 5.2 对话流程

**多轮对话支持：**
- 上下文连续，支持追问和澄清
- 限制：单次对话最多 20 轮
- 限制：总 token 不超过 128K（超出后自动截断早期对话）

**对话历史存储：**
- 保存到后端数据库（非 localStorage）
- 新增接口：`POST /api/v1/conversations` 创建对话，`GET /api/v1/conversations` 获取列表
- 前端 Pinia 缓存当前对话，刷新页面后从后端恢复

**用户输入：**
- 支持多行输入
- Enter 发送，Shift+Enter 换行
- 支持粘贴图片（未来扩展）

**AI 回答：**
- Markdown 渲染（支持代码块、表格、列表）
- 来源引用标注：`[文档1]` `[拓扑2]`
- 置信度评估：🔴🟡🟢 + 数据完整度 X/5
- 来源列表（可点击展开）

**交互：**
- 点击来源引用 → 侧边抽屉显示原文
- 复制回答按钮
- 重新生成按钮
- 对话历史列表（左侧栏）：显示标题 + 时间 + 第一条问题摘要

**API：**
- `POST /api/v1/query` — 发送问题，获取回答 + 来源

---

## 6. 主机监控页（/hosts）

### 6.1 主机列表

**视图：** 卡片网格 / 表格视图（可切换）

**每张卡片显示：**
- 主机名 + IP
- 操作系统图标（Linux/Windows）
- 状态 badge（online/offline）
- CPU / 内存 / 磁盘使用率（进度条）
- 负载 1/5/15

**数据源：**
- 批量查询：`GET /api/v1/hosts/status` (新接口)
- 或循环调用 `host-query status <ip>` (不推荐，性能差)

**筛选/排序：**
- 按状态筛选（online/offline/all）
- 按 CPU/内存/磁盘排序
- 按 IP/主机名搜索

### 6.2 主机详情

**布局：**
- 顶部：主机基本信息（名称、IP、OS、Zabbix 状态）
- 中间：实时指标面板（CPU/内存/磁盘/负载 当前值，无历史曲线）
- 底部：关联服务列表 + 关联文档（支持预览，不支持编辑）

**实时指标面板：**
- 4 个指标卡片：CPU 使用率、内存可用率、磁盘使用率、负载 1
- 每个卡片显示当前值 + 进度条
- 自动刷新（60s）
- 无历史曲线图（不做 Zabbix history.get）

**关联服务：**
- `GET /api/v1/host/:host_id/services` (复用现有接口)
- 服务列表：服务名 + 状态 + 角色
- 点击 → 跳转服务详情

**关联文档：**
- `GET /api/v1/host/:host_id/docs` (复用现有接口)
- 文档列表：标题 + 相关度
- 点击 → 右侧抽屉预览文档内容（Markdown 渲染）
- 不支持编辑（只读预览）

**API：**
- 基本信息：`GET /api/v1/hosts/status` 中的单条数据

---

## 7. 服务详情页（/services/:service_id）

### 7.1 服务拓扑

**布局：**
- 左侧：当前服务的拓扑图（Cytoscape.js）
- 右侧：服务信息面板

**拓扑图：**
- 中心节点：当前服务
- 上游节点（called_by）：左侧
- 下游节点（calls）：右侧
- 端口节点：底部

**交互：**
- 点击节点 → 跳转到该服务详情
- 点击边 → 显示调用协议/端口

### 7.2 服务信息

**基本信息：**
- 服务名 + ID
- 部署主机列表（可点击跳转）
- 端口列表
- 描述

**关联文档：**
- `GET /api/v1/service/:service_id/docs`
- 文档列表（标题 + 相关度）
- 点击 → 跳转文档详情

**关联主机：**
- `GET /api/v1/document/:doc_id/hosts`
- 主机列表 + 状态

---

## 8. 告警中心（/alerts）

### 8.1 活跃告警

**数据源：** `GET /api/v1/alerts/active` (新接口)

**告警类型：**
- 主机可达性告警（Zabbix triggers，ping 监控）
- 主机状态变更（available 字段从 true → false）

**表格列：**
- 时间（相对时间）
- 严重级别（badge）
- 问题标题（如"主机 10.33.17.100 不可达"）
- 影响服务
- 影响主机
- 状态（Triggered / Acknowledged / Resolved）
- 操作（Acknowledge / Resolve）

**筛选：**
- 按严重级别（Critical / Warning / Info）
- 按状态（Triggered / Acknowledged / Resolved）
- 按时间范围

### 8.2 告警统计

**图表：**
- 近 7 天告警趋势（折线图）
- 按严重级别分布（饼图）
- 按服务分布（柱状图）
- Top 10 高频告警（列表）

---

## 9. 权限验证系统

### 9.1 用户角色

| 角色 | 权限 |
|------|------|
| **admin** | 全部权限，包括用户管理、系统设置 |
| **operator** | 查看看板、工作台、主机、服务、告警；不能修改系统设置 |
| **viewer** | 只读权限，只能看板和查看，不能对话或操作告警 |

### 9.2 登录流程

**登录页（/login）：**
- 用户名 + 密码输入
- 记住登录状态（可选）
- 登录成功后跳转到 /dashboard

**认证方式：**
- JWT token（access_token + refresh_token）
- access_token 有效期：2 小时
- refresh_token 有效期：7 天
- Token 存储在 localStorage

**API 接口：**
```
POST /api/v1/auth/login
Body: { "username": "admin", "password": "xxx" }

Response: {
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": { "id": 1, "username": "admin", "role": "admin" }
}
```

```
POST /api/v1/auth/refresh
Body: { "refresh_token": "eyJ..." }

Response: { "access_token": "eyJ..." }
```

```
POST /api/v1/auth/logout
Headers: { "Authorization": "Bearer <access_token>" }
```

### 9.3 前端鉴权

**路由守卫：**
- 未登录 → 跳转 /login
- 已登录但无权限 → 显示 403 页面
- Token 过期 → 自动 refresh，失败则跳转 /login

**Axios 拦截器：**
- 请求拦截：自动添加 `Authorization: Bearer <token>` header
- 响应拦截：401 时尝试 refresh，失败则清除 token 跳转 /login

**组件级权限：**
- `v-if="user.role === 'admin'"` — 隐藏管理功能
- 告警操作（Acknowledge/Resolve）：仅 operator 和 admin
- 系统设置：仅 admin

### 9.4 用户管理（admin 功能）

**页面（/settings/users）：**
- 用户列表（用户名、角色、创建时间）
- 新增用户（用户名、密码、角色选择）
- 编辑用户（修改角色、重置密码）
- 删除用户

**API：**
```
GET /api/v1/users — 用户列表
POST /api/v1/users — 创建用户
PATCH /api/v1/users/:id — 更新用户
DELETE /api/v1/users/:id — 删除用户
```

---

## 10. 后端 API 扩展

前端需要但后端尚未提供的接口：

### 9.1 主机状态批量查询

```
GET /api/v1/hosts/status
```

**响应：**
```json
{
  "hosts": [
    {
      "host_id": "host_es_master_01",
      "name": "master-1",
      "ip": "10.33.17.100",
      "os": "CentOS 7",
      "available": true,
      "metrics": {
        "cpu": 0.46,
        "memory": 85.3,
        "disk": 72.1,
        "load1": 1.23
      }
    }
  ],
  "summary": {
    "total": 30,
    "online": 28,
    "offline": 2
  }
}
```

**实现：** 聚合 Zabbix API 批量查询 + rag 拓扑数据

### 9.2 全局拓扑查询

```
GET /api/v1/topology?service_id=all
```

**响应：**
```json
{
  "nodes": [
    {
      "id": "svc_es",
      "name": "elasticsearch",
      "type": "service",
      "status": "healthy",
      "hosts": ["host_es_master_01", ...],
      "impact_score": 5
    }
  ],
  "edges": [
    {
      "source": "svc_kibana",
      "target": "svc_es",
      "protocol": "http",
      "port": 9200
    }
  ]
}
```

**实现：** 遍历 Neo4j 所有 Service 节点 + 关联 Host 状态

### 9.3 活跃告警查询

```
GET /api/v1/alerts/active
```

**响应：**
```json
{
  "alerts": [
    {
      "id": "alert_001",
      "severity": "critical",
      "title": "Elasticsearch 集群异常",
      "affected_services": ["svc_es", "svc_kibana"],
      "affected_hosts": ["host_es_master_01"],
      "timestamp": "2026-06-30T09:15:00Z",
      "status": "triggered"
    }
  ],
  "total": 3
}
```

**实现：** 查询 Zabbix triggers + 关联 rag 拓扑

### 9.4 对话管理

**创建对话：**
```
POST /api/v1/conversations
Body: { "title": "ES 集群故障排查" }
```

**响应：**
```json
{
  "conversation_id": "conv_001",
  "title": "ES 集群故障排查",
  "created_at": "2026-06-30T09:00:00Z",
  "turn_count": 0,
  "total_tokens": 0
}
```

**获取对话列表：**
```
GET /api/v1/conversations
```

**响应：**
```json
{
  "conversations": [
    {
      "conversation_id": "conv_001",
      "title": "ES 集群故障排查",
      "created_at": "2026-06-30T09:00:00Z",
      "turn_count": 5,
      "total_tokens": 12500,
      "first_question": "nginx 502 怎么排查？"
    }
  ]
}
```

**发送消息（多轮对话）：**
```
POST /api/v1/conversations/:conversation_id/messages
Body: { "query": "影响哪些服务？", "context": [...] }
```

**响应：**
```json
{
  "answer": "影响 Kibana 和 Logstash 服务...",
  "sources": [...],
  "turn_count": 6,
  "total_tokens": 13200,
  "token_limit": 128000,
  "turn_limit": 20
}
```

**限制检查：**
- 如果 `turn_count >= 20`，返回错误提示"已达最大对话轮数"
- 如果 `total_tokens >= 128000`，自动截断早期对话，保留最近 10 轮

**实现：** SQLite 或 PostgreSQL 存储对话历史 + token 计数（使用 tiktoken 或简单字符估算）

---

## 11. 数据流

### 10.1 看板页数据流

```
页面加载
  ├─ GET /api/v1/topology?service_id=all → 拓扑结构
  ├─ GET /api/v1/hosts/status → 主机状态（批量）
  ├─ GET /api/v1/alerts/active → 活跃告警
  └─ 合并数据 → Cytoscape.js 渲染拓扑图

定时器（每 60s）
  ├─ GET /api/v1/hosts/status → 更新主机状态
  ├─ GET /api/v1/alerts/active → 更新告警
  ├─ 拓扑图节点颜色/动画更新
  └─ 告警时间线更新
```

### 10.2 工作台页数据流

```
页面加载
  └─ GET /api/v1/conversations → 获取对话历史列表

用户输入问题（新对话）
  ├─ POST /api/v1/conversations → 创建对话
  └─ POST /api/v1/conversations/:id/messages { query: "..." }
       ├─ 后端：查询改写 + ES 检索 + Neo4j 拓扑 + Rerank + LLM
       └─ 响应：{ answer, sources, turn_count, total_tokens }
            ├─ 前端：Markdown 渲染 + 来源引用标注
            └─ 检查限制：turn_count < 20 && total_tokens < 128K

用户追问（多轮对话）
  └─ POST /api/v1/conversations/:id/messages { query: "...", context: [...] }
       └─ 同上，返回累计 turn_count 和 total_tokens
```

---

## 12. 组件结构

```
src/
├── main.js                 # Vue 入口
├── App.vue                 # 根组件
├── router/
│   └── index.js            # 路由配置
├── stores/
│   ├── topology.js         # 拓扑数据（Pinia）
│   ├── hosts.js            # 主机状态
│   ├── alerts.js           # 告警数据
│   └── chat.js             # 对话历史
├── api/
│   ├── topology.js         # 拓扑 API
│   ├── hosts.js            # 主机 API
│   ├── alerts.js           # 告警 API
│   └── query.js            # RAG 查询 API
├── views/
│   ├── Dashboard.vue       # 看板页
│   ├── Workspace.vue       # 工作台页
│   ├── HostList.vue        # 主机列表
│   ├── HostDetail.vue      # 主机详情
│   ├── ServiceDetail.vue   # 服务详情
│   └── Alerts.vue          # 告警中心
├── components/
│   ├── layout/
│   │   ├── TopNav.vue      # 顶部栏
│   │   └── Sidebar.vue     # 左侧栏
│   ├── topology/
│   │   ├── TopologyGraph.vue    # Cytoscape 拓扑图
│   │   ├── TopologyNode.vue     # 自定义节点
│   │   └── TopologyEdge.vue     # 自定义边
│   ├── kpi/
│   │   └── KpiCard.vue     # KPI 卡片
│   ├── alerts/
│   │   ├── AlertTimeline.vue    # 告警时间线
│   │   └── AlertBadge.vue       # 告警 badge
│   ├── chat/
│   │   ├── ChatMessage.vue      # 对话消息
│   │   ├── ChatInput.vue        # 输入框
│   │   └── SourceRef.vue        # 来源引用
│   └── common/
│       ├── StatusBadge.vue      # 状态 badge
│       └── MetricChart.vue      # 指标曲线图
└── styles/
    └── design-tokens.css   # DESIGN.md 的 CSS 变量
```

---

## 13. 交互细节

### 12.1 故障传播可视化

**触发条件：** 主机 `available = false` 或服务状态异常

**视觉效果：**
1. 根因节点：红色脉动（`pulse 2s infinite`）
2. 传播路径：红色边线 + 粒子流动动画
3. 受影响节点：红色光晕（`box-shadow: 0 0 20px 5px rgba(242,73,92,0.4)`）
4. 其他节点：正常颜色，不受影响

**动画实现：**
- 脉动：CSS `@keyframes pulse` + `box-shadow` 变化
- 粒子流：SVG `<animateMotion>` 或 Canvas 粒子系统
- 光晕：CSS `box-shadow` 静态

### 12.2 全局搜索（⌘K）

**触发：** 点击搜索框 或 快捷键 ⌘K / Ctrl+K

**搜索范围：**
- 主机（按名称/IP）
- 服务（按名称/ID）
- 告警（按标题）
- 文档（按标题/内容）

**UI：** 模态对话框，输入即搜，回车跳转

### 12.3 时间范围选择器

**位置：** 顶部栏右侧

**预设：** 最近 15 分钟 / 1 小时 / 6 小时 / 24 小时 / 7 天

**自定义：** 日期范围选择器

**影响范围：** 所有指标曲线、告警统计、拓扑快照

---

## 14. 性能要求

| 指标 | 目标 | 测量方法 |
|------|------|----------|
| 首屏加载 | < 2s | Lighthouse FCP |
| 拓扑图渲染（30 节点） | < 500ms | Cytoscape.js ready 事件 |
| API 响应时间 | < 1s | 网络面板 |
| 轮询更新 | 无感知 | 不阻塞用户交互 |
| 内存占用 | < 200MB | Chrome Task Manager |

**优化策略：**
- 路由懒加载（`import()` 动态导入）
- 拓扑图数据缓存（Pinia + 60s TTL）
- 图表虚拟化（大数据量时只渲染可见区域）
- 防抖/节流（搜索输入、拖拽事件）

---

## 15. 可访问性

**颜色不是唯一信号：**
- 状态标识必须组合：颜色 + 图标 + 文字
- 红色盲友好：红色 + ⚠ 图标 + "严重" 文字

**键盘导航：**
- Tab 顺序：逻辑顺序（左→右，上→下）
- Enter/Space：激活按钮/链接
- Esc：关闭模态/抽屉

**对比度：**
- 文字：WCAG AA（4.5:1）
- 大文字：WCAG AA（3:1）

---

## 16. 测试策略

### 15.1 单元测试
- 组件渲染测试（Vue Test Utils）
- Pinia store 逻辑测试
- API mock 测试

### 15.2 E2E 测试
- 看板页加载 + 拓扑图渲染
- 工作台对话流程
- 主机列表筛选/排序

### 15.3 视觉回归测试
- Chromatic 或 Percy（截图对比）
- 关键页面：看板、工作台、主机详情

---

## 17. 部署

**开发环境：**
```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

**生产构建：**
```bash
npm run build  # dist/
```

**部署方式：**
- 静态文件托管（Nginx / Vercel / Netlify）
- Docker 容器（可选）

**环境变量：**
```
VITE_API_BASE_URL=http://localhost:8001/api/v1
```

---

## 18. 后续扩展

**二期+：**
- WebSocket 实时推送（替代轮询）
- Zabbix 告警接入（自动创建 Problem）
- 主机指标历史曲线（Zabbix history.get）
- 拓扑图编辑（拖拽调整布局）
- 自定义看板（用户可配置面板）
- 移动端适配（响应式布局）
- 多语言支持（i18n）

---

## 19. 决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-06-30 | Vue 3 + Vite | 国内社区活跃，上手快 |
| 2026-06-30 | Cytoscape.js | 图论原生，适合拓扑 + 故障传播 |
| 2026-06-30 | Naive UI | Vue 3 原生，深色主题支持好 |
| 2026-06-30 | 轮询 60s | 统一刷新间隔，平衡实时性和性能 |
| 2026-06-30 | 独立路由而非 Tab 切换 | 看板可单独投屏，互不干扰 |
| 2026-06-30 | Pinia 状态管理 | Vue 3 官方推荐，比 Vuex 更轻量 |
| 2026-06-30 | 多轮对话保存到后端 | 支持跨设备访问，持久化存储 |
| 2026-06-30 | 对话限制 20 轮 + 128K token | 控制成本，防止无限对话 |
| 2026-06-30 | 主机只做实时指标 | 不做历史曲线，简化一期范围 |
| 2026-06-30 | 关联文档只读预览 | 不支持编辑，降低复杂度 |
| 2026-06-30 | 告警来源 Zabbix triggers | 主机可达性监控（ping），复用现有告警 |
| 2026-06-30 | 需要权限验证系统 | 保护敏感运维数据，分级访问控制 |

---

## 20. 开放问题

**已全部解决，见 §18 决策记录。**

---

**下一步：** 用户审查此 spec → 确认后生成实施计划（writing-plans skill）
