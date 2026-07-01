<template>
  <div class="alerts">
    <div class="filter-bar">
      <div class="severity-filter">
        <button v-for="s in severityFilters" :key="s.key"
          :class="{ active: activeSeverity === s.key }"
          @click="activeSeverity = s.key">{{ s.label }}</button>
      </div>
    </div>

    <div v-if="!filteredAlerts.length" class="empty-state">
      <div class="empty-icon">✅</div>
      <h2>当前无活跃告警</h2>
      <p>所有主机状态正常</p>
    </div>

    <div v-else class="alert-table">
      <div v-for="a in filteredAlerts" :key="a.id" class="alert-row">
        <StatusBadge :status="a.severity" />
        <div class="alert-info">
          <div class="alert-title">{{ a.title }}</div>
          <div class="alert-meta">{{ a.affected_services?.length || 0 }} 个服务 · {{ formatTime(a.timestamp) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import StatusBadge from '../components/common/StatusBadge.vue'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

const activeSeverity = ref('all')
const alerts = ref([])

const severityFilters = [
  { key: 'all', label: '全部' },
  { key: 'critical', label: '严重' },
  { key: 'warning', label: '警告' }
]

onMounted(async () => {
  try {
    const res = await fetch('/api/v1/alerts/active')
    const data = await res.json()
    alerts.value = data.alerts || []
  } catch (e) {
    console.error('Failed to load alerts:', e)
  }
})

const filteredAlerts = computed(() => {
  if (activeSeverity.value === 'all') return alerts.value
  return alerts.value.filter(a => a.severity === activeSeverity.value)
})

const formatTime = (ts) => ts ? dayjs(ts).fromNow() : ''
</script>

<style scoped>
.alerts { display: flex; flex-direction: column; gap: var(--space-md); }

.filter-bar {
  padding: var(--space-md); background: var(--bg-surface);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-lg);
}
.severity-filter { display: flex; gap: 4px; }
.severity-filter button {
  padding: 6px 14px; background: var(--bg-elevated);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-sm);
  color: var(--text-secondary); cursor: pointer; font-size: var(--font-sm);
}
.severity-filter button.active { background: var(--info); color: #fff; border-color: var(--info); }

.empty-state {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: var(--space-2xl); color: var(--text-secondary);
}
.empty-icon { font-size: 48px; margin-bottom: var(--space-md); }

.alert-table {
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg); overflow: hidden;
}
.alert-row {
  display: flex; gap: var(--space-md); padding: var(--space-md);
  align-items: center; border-bottom: 1px solid var(--border-subtle);
}
.alert-row:last-child { border-bottom: none; }
.alert-info { flex: 1; }
.alert-title { font-size: var(--font-md); font-weight: 500; }
.alert-meta { font-size: var(--font-xs); color: var(--text-secondary); margin-top: 2px; }
</style>
