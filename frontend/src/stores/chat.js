import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  fetchConversations,
  createConversation,
  sendMessage
} from '../api/chat.js'

export const useChatStore = defineStore('chat', () => {
  // 状态
  const conversations = ref([])
  const currentId = ref(null)
  const messages = ref([])
  const sending = ref(false)
  const turnCount = ref(0)
  const totalTokens = ref(0)

  // 限制
  const MAX_TURNS = 20
  const MAX_TOKENS = 128000

  // 计算
  const currentConversation = computed(() =>
    conversations.value.find(c => c.conversation_id === currentId.value)
  )
  const canSend = computed(() =>
    !sending.value &&
    turnCount.value < MAX_TURNS &&
    totalTokens.value < MAX_TOKENS
  )

  // 加载对话列表
  async function loadConversations() {
    try {
      const data = await fetchConversations()
      conversations.value = data.conversations || []
    } catch (e) {
      console.error('Failed to load conversations:', e)
    }
  }

  // 创建新对话
  async function newConversation() {
    try {
      const defaultTitle = `对话 ${conversations.value.length + 1}`
      const data = await createConversation(defaultTitle)
      currentId.value = data.conversation_id
      messages.value = []
      turnCount.value = 0
      totalTokens.value = 0
      conversations.value.unshift(data)
      return data
    } catch (e) {
      console.error('Failed to create conversation:', e)
      return null
    }
  }

  // 发送消息
  async function send(query) {
    if (!currentId.value || !canSend.value) return null

    // 添加用户消息
    messages.value.push({
      role: 'user',
      content: query,
      timestamp: new Date().toISOString()
    })

    sending.value = true
    try {
      // 计算上下文（最近 N 轮）
      const context = messages.value.slice(-10).map(m => ({
        role: m.role,
        content: m.content
      }))

      const data = await sendMessage(currentId.value, query, context)

      // 添加 AI 回复
      messages.value.push({
        role: 'assistant',
        content: data.answer,
        sources: data.sources || [],
        confidence: data.confidence || 'medium',
        timestamp: new Date().toISOString()
      })

      turnCount.value = data.turn_count || turnCount.value + 1
      totalTokens.value = data.total_tokens || 0

      return data
    } catch (e) {
      messages.value.push({
        role: 'assistant',
        content: `**错误：** ${e.message}`,
        timestamp: new Date().toISOString()
      })
      return null
    } finally {
      sending.value = false
    }
  }

  // 选择对话
  function selectConversation(id) {
    currentId.value = id
    messages.value = []
    turnCount.value = 0
    totalTokens.value = 0
  }

  return {
    conversations, currentId, messages,
    sending, turnCount, totalTokens,
    currentConversation, canSend,
    loadConversations, newConversation,
    send, selectConversation
  }
})
