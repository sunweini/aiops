<template>
  <div class="host-detail">
    <button class="back-btn" @click="$router.push('/hosts')">← 返回主机列表</button>

    <div class="info-card">
      <div class="info-header">
        <StatusBadge :status="host.available ? 'healthy' : 'critical'" />
        <h2>{{ host.name || host.host_id }}</h2>
        <span class="ip">{{ host.ip }}</span>
      </div>
      <div class="info-body">
        <div class="info-row"><span>主机 ID</span><span class="mono">{{ host.host_id }}</span></div>
        <div class="info-row"><span>CPU</span><span>{{ formatMetric(host.metrics?.cpu) }}</span></div>
        <div class="info-row"><span>内存</span><span>{{ formatMetric(host.metrics?.memory) }}</span></div>
        <div class="info-row"><span>磁盘</span><span>{{ formatMetric(host.metrics?.disk) }}</span></div>
        <div class="info-row"><span>负载</span><span>{{ host.metrics?.load1 != null ? host.metrics.load1 : 'N/A' }}</span></div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-header">实时指标</div>
      <div class="metric-cards">
        <div class="metric-card" v-for="m in metrics" :key="m.key">
          <div class="metric-val" :style="{ color: m.color }">{{ m.value }}</div>
          <div class="metric-label">{{ m.label }}</div>
          <div class="metric-bar"><div class="bar-fill" :style="{ width: m.barWidth, background: m.color }"></div></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import StatusBadge from '../components/common/StatusBadge.vue'

const route = useRoute()
const host = ref({ metrics: {} })

onMounted(async () => {
  try {
    const res = await fetch('/api/v1/hosts/status')
    const data = await res.json()
    const found = (data.hosts || []).find(h => h.host_id === route.params.host_id)
    if (found) host.value = found
  } catch (e) {
    console.error(e)
  }
})

const metrics = computed(() => {
  const m = host.value.metrics || {}
  const items = [
    { key: 'cpu', label: 'CPU 使用率', value: formatMetric(m.cpu), raw: m.cpu },
    { key: 'memory', label: '内存可用率', value: formatMetric(m.memory), raw: m.memory },
    { key: 'disk', label: '磁盘使用率', value: formatMetric(m.disk), raw: m.disk },
    { key: 'load', label: '负载 (1m)', value: m.load1 != null ? m.load1 : 'N/A', raw: m.load1 }
  ]
  return items.map(i => ({
    ...i,
    color: !i.raw ? 'var(--unknown)' : i.raw > 90 ? 'var(--critical)' : i.raw > 75 ? 'var(--warning)' : 'var(--healthy)',
    barWidth: i.raw != null ? Math.min(i.raw, 100) + '%' : '0%'
  }))
})

function formatMetric(v) { return v != null ? v + '%' : 'N/A' }
</script>

<style scoped>
.host-detail { display: flex; flex-direction: column; gap: var(--space-lg); }

.back-btn {
  align-self: flex-start; padding: 8px 16px;
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm); color: var(--text-secondary);
  cursor: pointer; font-size: var(--font-sm);
}
.back-btn:hover { color: var(--text-primary); }

.info-card {
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg); overflow: hidden;
}

.info-header {
  display: flex; align-items: center; gap: var(--space-md);
  padding: var(--space-md); background: var(--bg-elevated);
}
.info-header h2 { font-family: var(--font-display); font-size: var(--font-lg); }
.ip { font-family: var(--font-data); color: var(--text-secondary); font-size: var(--font-sm); }

.info-body { padding: var(--space-md); }
.info-row {
  display: flex; justify-content: space-between; padding: 8px 0;
  border-bottom: 1px solid var(--border-subtle); font-size: var(--font-sm);
}
.info-row:last-child { border-bottom: none; }
.mono { font-family: var(--font-data); font-variant-numeric: tabular-nums; }

.panel {
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg); overflow: hidden;
}
.panel-header {
  padding: 12px var(--space-md); border-bottom: 1px solid var(--border-subtle);
  font-family: var(--font-display); font-weight: 600; font-size: var(--font-md);
}

.metric-cards {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-md);
  padding: var(--space-md);
}

.metric-card {
  text-align: center; padding: var(--space-md);
  background: var(--bg-elevated); border-radius: var(--radius-md);
}
.metric-val {
  font-family: var(--font-data); font-size: var(--font-2xl);
  font-weight: 600; font-variant-numeric: tabular-nums;
}
.metric-label { font-size: var(--font-xs); color: var(--text-secondary); margin: 4px 0; }
.metric-bar { height: 6px; background: var(--bg-canvas); border-radius: 3px; overflow: hidden; }
</style>
