<template>
  <div class="dashboard">
    <!-- KPI 卡片行 -->
    <div class="kpi-row">
      <KpiCard label="正常主机" value="28/30" status="healthy" />
      <KpiCard label="活跃告警" value="3" status="critical" />
      <KpiCard label="受影响服务" value="2" status="warning" />
      <KpiCard label="平均发现时间" value="4.2m" status="info" />
    </div>

    <!-- 主内容区 -->
    <div class="content-row">
      <!-- 拓扑图面板 -->
      <div class="panel">
        <div class="panel-header">服务拓扑图 — 故障传播视图</div>
        <div class="panel-body">
          <TopologyGraph
            :nodes="mockNodes"
            :edges="mockEdges"
            height="350px"
            @node-click="handleNodeClick"
          />
        </div>
      </div>

      <!-- 告警时间线面板 -->
      <div class="panel">
        <div class="panel-header">告警时间线</div>
        <div class="panel-body">
          <AlertTimeline :alerts="mockAlerts" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import KpiCard from '../components/kpi/KpiCard.vue'
import AlertTimeline from '../components/alerts/AlertTimeline.vue'
import TopologyGraph from '../components/topology/TopologyGraph.vue'

const mockAlerts = [
  {
    id: 'alert_001',
    severity: 'critical',
    title: 'Elasticsearch 集群异常',
    affectedServices: ['svc_es', 'svc_kibana'],
    timestamp: '2026-06-30T09:15:00Z'
  },
  {
    id: 'alert_002',
    severity: 'warning',
    title: 'Kibana 连接超时',
    affectedServices: ['svc_kibana'],
    timestamp: '2026-06-30T09:12:00Z'
  },
  {
    id: 'alert_003',
    severity: 'warning',
    title: 'Logstash 数据延迟',
    affectedServices: ['svc_logstash'],
    timestamp: '2026-06-30T09:10:00Z'
  }
]

const mockNodes = [
  { id: 'svc_nginx', label: 'Nginx', status: 'healthy' },
  { id: 'svc_app01', label: 'App01', status: 'healthy' },
  { id: 'svc_app02', label: 'App02', status: 'healthy' },
  { id: 'svc_es', label: 'ES', status: 'critical' },
  { id: 'svc_kibana', label: 'Kibana', status: 'blast' },
  { id: 'svc_logstash', label: 'Logstash', status: 'blast' },
  { id: 'svc_db', label: 'SQLServer', status: 'healthy' }
]

const mockEdges = [
  { source: 'svc_nginx', target: 'svc_app01' },
  { source: 'svc_nginx', target: 'svc_app02' },
  { source: 'svc_app01', target: 'svc_es' },
  { source: 'svc_app02', target: 'svc_es' },
  { source: 'svc_kibana', target: 'svc_es' },
  { source: 'svc_logstash', target: 'svc_es' },
  { source: 'svc_app01', target: 'svc_db' },
  { source: 'svc_app02', target: 'svc_db' }
]

const handleNodeClick = (nodeId) => {
  console.log('Node clicked:', nodeId)
}
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-md);
}

.content-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--space-md);
}

.panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.panel-header {
  padding: 12px var(--space-md);
  border-bottom: 1px solid var(--border-subtle);
  font-family: var(--font-display);
  font-weight: 600;
  font-size: var(--font-md);
}

.panel-body {
  padding: var(--space-md);
  min-height: 300px;
}
</style>
