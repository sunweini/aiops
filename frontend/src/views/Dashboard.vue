<template>
  <div class="dashboard">
    <!-- KPI 卡片行 -->
    <div class="kpi-row">
      <KpiCard label="正常主机" :value="`${onlineHosts}/${totalHosts}`" :status="onlineHosts === totalHosts ? 'healthy' : 'critical'" />
      <KpiCard label="活跃告警" :value="String(alerts.length)" :status="alerts.length === 0 ? 'healthy' : alerts.length <= 2 ? 'warning' : 'critical'" />
      <KpiCard label="受影响服务" :value="String(affectedServices)" :status="affectedServices === 0 ? 'healthy' : 'warning'" />
      <KpiCard label="服务总数" :value="String(services.length)" status="info" />
    </div>

    <!-- 主内容区 -->
    <div class="content-row">
      <!-- 拓扑图面板 -->
      <div class="panel">
        <div class="panel-header">
          服务拓扑图
          <button class="layout-switch" @click="cycleLayout">{{ layoutName }}</button>
        </div>
        <div class="panel-body">
          <TopologyGraph
            v-if="topoNodes.length"
            :nodes="topoNodes"
            :edges="topoEdges"
            :layout="currentLayout"
            height="350px"
            @node-click="handleNodeClick"
          />
          <div v-else class="loading">加载拓扑数据中...</div>
        </div>
      </div>

      <!-- 告警时间线面板 -->
      <div class="panel">
        <div class="panel-header">告警时间线</div>
        <div class="panel-body">
          <AlertTimeline :alerts="alerts" />
          <div v-if="!alerts.length" class="no-alerts">暂无活跃告警</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import KpiCard from '../components/kpi/KpiCard.vue'
import AlertTimeline from '../components/alerts/AlertTimeline.vue'
import TopologyGraph from '../components/topology/TopologyGraph.vue'

const router = useRouter()

// API data
const services = ref([])
const hosts = ref([])
const alerts = ref([])
const edges = ref([])
const loading = ref(true)

// Layout switching
const layouts = ['cose', 'grid', 'circle']
const layoutIndex = ref(0)
const currentLayout = ref('cose')
const layoutName = computed(() => ({ cose: '力导向', grid: '网格', circle: '环形' }[currentLayout.value]))
function cycleLayout() {
  layoutIndex.value = (layoutIndex.value + 1) % layouts.length
  currentLayout.value = layouts[layoutIndex.value]
}

// Polling
let timer = null

// Map API data to topology format
const topoNodes = computed(() =>
  services.value.map(s => ({
    id: s.id,
    label: s.name || s.id,
    status: 'healthy'
  }))
)

const topoEdges = computed(() =>
  edges.value.map(e => ({ source: e.source, target: e.target }))
)

const onlineHosts = computed(() => hosts.value.filter(h => h.available).length)
const totalHosts = computed(() => hosts.value.length)
const affectedServices = computed(() => 0)

async function fetchData() {
  try {
    const [topoRes, hostsRes, alertsRes] = await Promise.all([
      fetch('/api/v1/topology/all'),
      fetch('/api/v1/hosts/status'),
      fetch('/api/v1/alerts/active')
    ])
    const topo = await topoRes.json()
    const hostsData = await hostsRes.json()
    const alertsData = await alertsRes.json()

    services.value = topo.services || []
    edges.value = topo.edges || []
    hosts.value = hostsData.hosts || []
    alerts.value = alertsData.alerts || []
  } catch (e) {
    console.error('Failed to fetch dashboard data:', e)
  } finally {
    loading.value = false
  }
}

function handleNodeClick(nodeId) {
  console.log('Node clicked:', nodeId)
  // TODO: route to service detail when available
}

onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 60000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px var(--space-md);
  border-bottom: 1px solid var(--border-subtle);
  font-family: var(--font-display);
  font-weight: 600;
  font-size: var(--font-md);
}

.layout-switch {
  padding: 4px 10px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--font-xs);
}
.layout-switch:hover { color: var(--text-primary); }

.panel-body {
  padding: var(--space-md);
  min-height: 300px;
}

.loading, .no-alerts {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-disabled);
  font-size: var(--font-sm);
}
</style>
