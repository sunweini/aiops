# Design System — AIOps 运维监控平台

## Product Context
- **What this is:** AIOps 运维监控平台前端 — 集成服务拓扑可视化、主机实时监控、故障影响分析、RAG 知识库对话
- **Who it's for:** 运维团队（日常值班）+ 管理层（总览面板）
- **Space/industry:** AIOps / IT 运维监控，同类：Grafana、Datadog、PagerDuty、Dynatrace
- **Project type:** Dashboard（实时看板）+ 工作台（对话查询），双模式独立路由

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian（工业功能主义）
- **Decoration level:** Intentional — 微妙深度层次，不扁平不花哨
- **Mood:** 专业、克制、数据密度高、故障一目了然
- **Reference sites:** Grafana (深色数据面板), Datadog (企业级简洁), Dynatrace Smartscape (故障传播可视化)

## Typography
- **Display/Hero:** Instrument Sans — 专业感强，标题/导航/KPI 数字
- **Body:** DM Sans — 屏幕可读性优秀，正文/描述/对话内容
- **UI/Labels:** DM Sans — 统一正文
- **Data/Tables:** Geist Mono — 等宽数字对齐，监控指标/表格数据，`font-variant-numeric: tabular-nums`
- **Code:** Geist Mono
- **Loading:** Google Fonts CDN (`https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap`)
- **Scale:**
  - `--font-xs: 11px` — 轴标签/脚注（绝对最小）
  - `--font-sm: 12px` — 辅助文字/表格单元格
  - `--font-md: 13px` — 正文/指标值
  - `--font-lg: 16px` — 面板标题/KPI 标签
  - `--font-xl: 24px` — 大 KPI 数字
  - `--font-2xl: 32px` — 看板头部指标
  - `--font-3xl: 36px` — 英雄区标题

## Color
- **Approach:** Restrained — 颜色是状态信号，不是装饰
- **Background layers (深蓝灰，由深到浅):**
  - `--bg-canvas: #0a0e1a` — 最外层背景（带蓝调的深黑）
  - `--bg-surface: #131926` — 面板/卡片背景
  - `--bg-elevated: #1c2433` — 浮层/下拉/工具提示
  - `--border-subtle: #2c3235` — 微弱边框
- **Text:**
  - `--text-primary: rgba(255,255,255,0.87)` — 主要文字
  - `--text-secondary: rgba(255,255,255,0.55)` — 次要/辅助
  - `--text-disabled: rgba(255,255,255,0.30)` — 禁用/占位
- **Semantic status (去饱和，长时间不刺眼):**
  - `--critical: #F2495C` — 严重故障/主机宕机（红）
  - `--warning: #FADE2A` — 性能告警/阈值逼近（黄）
  - `--healthy: #73BF69` — 运行正常（绿）
  - `--info: #5794F2` — 信息/链接/交互（蓝）
  - `--unknown: #8E8E8E` — 无数据/断开（灰）
- **Fault propagation (故障传播专用):**
  - `--fault-root: #FF4D4D` — 脉动根因节点
  - `--fault-path: #F2495C` — 传播路径线
  - `--fault-blast: rgba(242,73,92,0.15)` — 受影响节点光晕
- **Dark mode:** 默认深色主题（运维场景），浅色主题作为可选

## Spacing
- **Base unit:** 8px
- **Density:** Comfortable — 信息密度高但不拥挤
- **Scale:** `--space-xs: 4px` / `--space-sm: 8px` / `--space-md: 16px` / `--space-lg: 24px` / `--space-xl: 32px` / `--space-2xl: 48px` / `--space-3xl: 64px`

## Layout
- **Approach:** Hybrid — 网格纪律（面板区）+ 拓扑自由（图可视化）
- **Navigation:** 左侧边栏（200px）+ 顶部栏（48px）+ 主内容区
- **Grid:** 面板区使用 CSS Grid，`grid-template-columns: repeat(auto-fit, minmax(300px, 1fr))`
- **Max content width:** 100%（看板全屏）
- **Border radius:** `sm: 4px` / `md: 6px` / `lg: 8px` / `full: 9999px`
- **Breakpoints:** `sm: 640px` / `md: 768px` / `lg: 1024px` / `xl: 1280px`

## Motion
- **Approach:** Intentional — 状态过渡、故障脉冲、数据流动画
- **Easing:** `enter: ease-out` / `exit: ease-in` / `move: ease-in-out`
- **Duration:**
  - `micro: 50-100ms` — hover/active 反馈
  - `short: 150-250ms` — 面板展开/折叠
  - `medium: 250-400ms` — 页面切换/路由过渡
  - `long: 400-700ms` — 故障脉动动画循环
- **Fault animations:**
  - 根因节点：`pulse 2s infinite` — 红色光晕呼吸
  - 传播路径：`flow 1s linear infinite` — 红色粒子沿线流动
  - 受影响节点：静态红色光晕 `box-shadow: 0 0 20px 5px rgba(242,73,92,0.4)`

## Component Patterns

### Status Badge
```html
<span class="badge critical">
  <span class="badge-dot"></span>严重故障
</span>
```
永远不单独使用颜色。必须组合：颜色 + 图标 + 文字标签。

### KPI Card
```html
<div class="kpi-card">
  <div class="kpi-label">正常主机</div>
  <div class="kpi-value healthy">28/30</div>
</div>
```
KPI 数字使用 `--font-2xl`，颜色跟随状态。

### Panel
```html
<div class="panel">
  <div class="panel-header">面板标题</div>
  <div class="panel-body">内容区</div>
</div>
```

### Topology Node
```html
<div class="topo-node critical">ES ⚠ DOWN</div>
```
节点状态通过 CSS class 切换（`healthy` / `warning` / `critical` / `blast`）。

## Key Features

### 1. 全局看板（/dashboard）
- KPI 汇总行：正常主机数、活跃告警数、受影响服务数、平均发现时间
- 服务拓扑图（hero element）：Cytoscape.js 渲染，节点按状态着色，故障脉动动画
- 告警时间线：按问题分组（非单条告警），展开查看详情

### 2. 工作台（/workspace）
- 对话查询界面：类 ChatGPT 风格，输入问题获取 RAG 知识库答案
- 来源引用：每条事实标注来源标记（文档/拓扑），置信度评估

### 3. 故障传播可视化（核心特性）
- 根因节点：最亮红色 + 脉动动画
- 传播路径：红色边线 + 流动粒子动画
- 影响范围：受影响节点红色光晕
- 影响分数：每个节点显示"如果它挂了，影响多少下游服务"

## Technology Stack
- **Framework:** Vue 3 + Composition API
- **Build tool:** Vite
- **Topology visualization:** Cytoscape.js
- **UI components:** Naive UI or Element Plus (TBD)
- **Routing:** Vue Router
- **State management:** Pinia
- **HTTP client:** Axios or fetch

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-30 | Initial design system created | 基于 Grafana/Datadog/PagerDuty/Dynatrace 调研，定位"专业运维工具，故障一目了然" |
| 2026-06-30 | 深蓝灰底 #0a0e1a | 比纯黑更有层次，比纯蓝更专业，接近中国 AIOps 审美但更克制 |
| 2026-06-30 | 去饱和状态色 | 长时间值班不刺眼，#F2495C 替代纯红 #FF0000 |
| 2026-06-30 | Instrument Sans + DM Sans + Geist Mono | 兼顾辨识度和数据密度，tabular-nums 对齐指标 |
| 2026-06-30 | 故障传播路径动画 | 杀手特性 — 红色粒子沿拓扑边流动，大多数工具只有静态变色 |
| 2026-06-30 | 影响分数标注 | 每个节点显示"影响多少下游"，高影响节点即使健康也有微光边框 |
