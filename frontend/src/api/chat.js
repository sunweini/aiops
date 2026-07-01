import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const http = axios.create({
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' }
})

/**
 * 获取对话历史列表
 * GET /api/v1/conversations
 */
export async function fetchConversations() {
  const res = await http.get(`${API_BASE}/conversations`)
  return res.data
}

/**
 * 创建新对话
 * POST /api/v1/conversations
 */
export async function createConversation(title) {
  const res = await http.post(`${API_BASE}/conversations`, { title })
  return res.data
}

/**
 * 发送消息（单次/多轮对话）
 * POST /api/v1/conversations/:id/messages
 */
export async function sendMessage(conversationId, query, context) {
  const payload = { query }
  if (context) payload.context = context
  const res = await http.post(
    `${API_BASE}/conversations/${conversationId}/messages`,
    payload
  )
  return res.data
}
