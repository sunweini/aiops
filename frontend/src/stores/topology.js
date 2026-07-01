import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { fetchTopology, fetchHostsStatus, fetchActiveAlerts } from '../api/topology.js'

export const useTopologyStore = defineStore('topology', () => {
  // 状态
  const nodes = ref([])
  const edges = ref([])
  const hosts = ref({ total: 0, online: 0, offline: 0 })
  const alerts = ref([])
  const loading = ref(false)
  const error = ref(null)

  // 计算属性
  const healthyCount = computed(() => hosts.value.online)
  const totalHosts = computed(() => hosts.value.total)
  const alertCount = computed(() => alerts.value.length)

  // API 调用
  let pollTimer = null

  async function loadData() {
    loading.value = true
    error.value = null
    try {
      const [topo, hostStatus, activeAlerts] = await Promise.all([
        fetchTopology(),
        fetchHostsStatus(),
        fetchActiveAlerts()
      ])

      // 处理拓扑
      if (topo?.nodes) {
        nodes.value = topo.nodes.map(n => ({
          id: n.id,
          label: n.name || n.id,
          status: mapHostStatusToNodeStatus(n, hostStatus)
        }))
      }
      if (topo?.edges) {
        edges.value = topo.edges
      }

      // 处理主机状态
      if (hostStatus) {
        hosts.value = {
          total: hostStatus.summary?.total || 0,
          online: hostStatus.summary?.online || 0,
          offline: hostStatus.summary?.offline || 0
        }
      }

      // 处理告警
      if (activeAlerts?.alerts) {
        alerts.value = activeAlerts.alerts
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  function startPolling(intervalMs = 60000) {
    loadData()
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(loadData, intervalMs)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  return {
    nodes, edges, hosts, alerts,
    loading, error,
    healthyCount, totalHosts, alertCount,
    loadData, startPolling, stopPolling
  }
})

/**
 * 根据主机状态映射节点颜色
 * 简化版：如果主机 offline > 0 则 critical
 */
function mapHostStatusToNodeStatus(node, hostStatus) {
  if (!hostStatus?.hosts) return 'healthy'
  const nodeHosts = node.hosts || []
  const offline = hostStatus.hosts.filter(h =>
    nodeHosts.includes(h.host_id) && !h.available
  )
  return offline.length > 0 ? 'critical' : 'healthy'
}
