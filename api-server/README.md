aiops-api-server — AIOps 平台后端服务

独立容器，提供前端所需的后端 API：
- 对话管理（SQLite 持久化）
- JWT 认证
- 用户管理
- 主机状态（代理 rag-api Neo4j 数据）
- 全局拓扑（代理 rag-api）
- 活跃告警（未来对接 Zabbix triggers）

**注意：** 这是 rag RAG 知识库 API 的补充，不是替代。
RAG 查询仍然走 rag-api（:8001）。
