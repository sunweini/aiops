<template>
  <div class="host-list">
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="view-toggle">
        <button :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'">卡片视图</button>
        <button :class="{ active: viewMode === 'table' }" @click="viewMode = 'table'">表格视图</button>
      </div>
      <div class="status-filter">
        <button
          v-for="f in filters"
          :key="f.key"
          :class="{ active: activeFilter === f.key }"
          @click="activeFilter = f.key"
        >{{ f.label }}</button>
      </div>
      <input class="search" v-model="searchQuery" placeholder="搜索 IP / 主机名...">
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>加载主机数据中...</p>
    </div>

    <!-- 卡片视图 -->
    <div v-else-if="viewMode === 'card'" class="card-grid">
      <div v-for="h in filteredHosts" :key="h.host_id" class="host-card" @click="$router.push(`/hosts/${h.host_id}`)">
        <div class="card-header">
          <StatusBadge :status="h.available ? 'healthy' : 'critical'" />
          <span class="host-ip">{{ h.ip }}</span>
        </div>
        <div class="card-body">
          <div class="host-name">{{ h.name || h.host_id }}</div>
          <div class="metric-row">
            <span class="metric-label">CPU</span>
            <div class="metric-bar">
              <div class="bar-fill" :style="{ width: metricWidth(h.metrics?.cpu), background: metricColor(h.metrics?.cpu) }"></div>
            </div>
            <span class="metric-value">{{ formatMetric(h.metrics?.cpu) }}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">内存</span>
            <div class="metric-bar">
              <div class="bar-fill" :style="{ width: metricWidth(h.metrics?.memory), background: metricColor(h.metrics?.memory) }"></div>
            </div>
            <span class="metric-value">{{ formatMetric(h.metrics?.memory) }}</span>
          </div>
          <div class="metric-row">
            <span class="metric-label">磁盘</span>
            <div class="metric-bar">
              <div class="bar-fill" :style="{ width: metricWidth(h.metrics?.disk), background: metricColor(h.metrics?.disk) }"></div>
            </div>
            <span class="metric-value">{{ formatMetric(h.metrics?.disk) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 表格视图 -->
    <div v-else class="table-wrapper">
      <table class="host-table">
        <thead>
          <tr>
            <th @click="sortBy = 'name'">主机名</th>
            <th @click="sortBy = 'ip'">IP</th>
            <th @click="sortBy = 'available'">状态</th>
            <th @click="sortBy = 'cpu'">CPU</th>
            <th @click="sortBy = 'memory'">内存</th>
            <th @click="sortBy = 'disk'">磁盘</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="h in sortedHosts" :key="h.host_id" @click="$router.push(`/hosts/${h.host_id}`)">
            <td>{{ h.name || h.host_id }}</td>
            <td class="mono">{{ h.ip }}</td>
            <td><StatusBadge :status="h.available ? 'healthy' : 'critical'" /></td>
            <td>{{ formatMetric(h.metrics?.cpu) }}</td>
            <td>{{ formatMetric(h.metrics?.memory) }}</td>
            <td>{{ formatMetric(h.metrics?.disk) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!loading && !filteredHosts.length" class="empty-state">
      <p>没有匹配的主机</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import StatusBadge from '../components/common/StatusBadge.vue'

const viewMode = ref('card')
const activeFilter = ref('all')
const searchQuery = ref('')
const sortBy = ref('name')
const hosts = ref([])
const loading = ref(true)

const filters = [
  { key: 'all', label: '全部' },
  { key: 'online', label: '在线' },
  { key: 'offline', label: '离线' }
]

onMounted(async () => {
  try {
    loading.value = true
    const res = await fetch('/api/v1/hosts/status')
    const data = await res.json()
    hosts.value = data.hosts || []
  } catch (e) {
    console.error('Failed to load hosts:', e)
  } finally {
    loading.value = false
  }
})

const filteredHosts = computed(() => {
  let list = hosts.value
  if (activeFilter.value === 'online') list = list.filter(h => h.available)
  if (activeFilter.value === 'offline') list = list.filter(h => !h.available)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(h =>
      (h.ip || '').toLowerCase().includes(q) ||
      (h.name || '').toLowerCase().includes(q)
    )
  }
  return list
})

const sortedHosts = computed(() => {
  const list = [...filteredHosts.value]
  list.sort((a, b) => {
    let va = a[sortBy.value], vb = b[sortBy.value]
    if (typeof va === 'string') return va.localeCompare(vb || '')
    return (va || 0) - (vb || 0)
  })
  return list
})

function metricWidth(v) { return Math.min((v || 0), 100) + '%' }
function metricColor(v) {
  if (!v) return 'var(--unknown)'
  if (v > 90) return 'var(--critical)'
  if (v > 75) return 'var(--warning)'
  return 'var(--healthy)'
}
function formatMetric(v) { return v != null ? v + '%' : 'N/A' }
</script>

<style scoped>
.host-list { display: flex; flex-direction: column; gap: var(--space-md); }

.filter-bar {
  display: flex; gap: var(--space-md); align-items: center;
  padding: var(--space-md); background: var(--bg-surface);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-lg);
}

.view-toggle, .status-filter { display: flex; gap: 4px; }
.view-toggle button, .status-filter button {
  padding: 6px 12px; background: var(--bg-elevated);
  border: 1px solid var(--border-subtle); border-radius: var(--radius-sm);
  color: var(--text-secondary); cursor: pointer; font-size: var(--font-sm);
}
.view-toggle button.active, .status-filter button.active {
  background: var(--info); color: #fff; border-color: var(--info);
}

.search {
  flex: 1; max-width: 300px; padding: 6px 12px;
  background: var(--bg-elevated); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md); color: var(--text-primary);
  font-size: var(--font-sm);
}

.card-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-md);
}

.host-card {
  background: var(--bg-surface); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg); overflow: hidden; cursor: pointer;
  transition: border-color 0.15s;
}
.host-card:hover { border-color: var(--info); }

.card-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-sm) var(--space-md);
  background: var(--bg-elevated); font-size: var(--font-xs);
}
.host-ip { font-family: var(--font-data); color: var(--text-secondary); }

.card-body { padding: var(--space-md); }
.host-name { font-weight: 500; margin-bottom: var(--space-sm); }

.metric-row {
  display: flex; align-items: center; gap: 8px;
  font-size: var(--font-xs); margin-bottom: 4px;
}
.metric-label { width: 28px; color: var(--text-secondary); }
.metric-bar {
  flex: 1; height: 6px; background: var(--bg-elevated);
  border-radius: 3px; overflow: hidden;
}
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.metric-value {
  width: 40px; text-align: right; font-family: var(--font-data);
  font-variant-numeric: tabular-nums;
}

.table-wrapper { overflow-x: auto; }
.host-table {
  width: 100%; border-collapse: collapse;
  background: var(--bg-surface); border-radius: var(--radius-lg);
  overflow: hidden;
}
.host-table th {
  padding: 10px var(--space-md); background: var(--bg-elevated);
  text-align: left; font-size: var(--font-sm); color: var(--text-secondary);
  cursor: pointer; user-select: none;
}
.host-table td {
  padding: 8px var(--space-md); font-size: var(--font-sm);
  border-bottom: 1px solid var(--border-subtle); cursor: pointer;
}
.host-table tr:hover td { background: var(--bg-elevated); }
.mono { font-family: var(--font-data); font-variant-numeric: tabular-nums; }

.empty-state {
  text-align: center; padding: var(--space-2xl);
  color: var(--text-secondary);
}

.loading-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: var(--space-3xl); color: var(--text-secondary);
}

.spinner {
  width: 40px; height: 40px;
  border: 3px solid var(--border-subtle);
  border-top-color: var(--info);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: var(--space-md);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
