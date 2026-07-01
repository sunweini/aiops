import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/**
 * 获取全局拓扑（所有服务 + 边）
 * GET /api/v1/topology?service_id=all
 */
export async function fetchTopology() {
  const res = await axios.get(`${API_BASE}/topology`, {
    params: { service_id: 'all' }
  })
  return res.data
}

/**
 * 获取主机状态（批量）
 * GET /api/v1/hosts/status
 */
export async function fetchHostsStatus() {
  const res = await axios.get(`${API_BASE}/hosts/status`)
  return res.data
}

/**
 * 获取活跃告警
 * GET /api/v1/alerts/active
 */
export async function fetchActiveAlerts() {
  const res = await axios.get(`${API_BASE}/alerts/active`)
  return res.data
}
