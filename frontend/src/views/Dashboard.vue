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
          <div class="placeholder">拓扑图待实现</div>
        </div>
      </div>

      <!-- 告警时间线面板 -->
      <div class="panel">
        <div class="panel-header">告警时间线</div>
        <div class="panel-body">
          <div class="placeholder">告警时间线待实现</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import KpiCard from '../components/kpi/KpiCard.vue'
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

.placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-disabled);
  font-size: var(--font-sm);
}
</style>
