<template>
  <div class="workspace">
    <!-- 对话历史侧栏 -->
    <aside class="history-sidebar">
      <div class="sidebar-header">
        对话历史
        <button v-if="chatStore.conversations.length" class="clear-btn" @click="handleClear">清空</button>
      </div>
      <ConversationList
        :conversations="chatStore.conversations"
        :activeId="chatStore.currentId"
        @new="handleNew"
        @select="handleSelect"
        @delete="handleDelete"
      />
    </aside>

    <!-- 主对话区 -->
    <div class="chat-area">
      <!-- 空状态 -->
      <div v-if="!chatStore.currentId" class="empty-state">
        <div class="empty-icon">💬</div>
        <h2>AIOps 知识库</h2>
        <p>你可以问我：</p>
        <ul>
          <li>nginx 502 怎么排查？</li>
          <li>host_es_master_01 影响什么服务？</li>
          <li>K3s 集群的 SOP 是什么？</li>
        </ul>
        <p class="limit-note">每个对话最多 20 轮 · 128K token</p>
      </div>

      <!-- 消息流 -->
      <div v-else class="message-flow" ref="flowRef">
        <ChatMessage
          v-for="(msg, i) in chatStore.messages"
          :key="i"
          :message="msg"
          @source-click="handleSourceClick"
        />

        <!-- 发送中提示 -->
        <div v-if="chatStore.sending" class="sending-hint">
          <div class="sending-dot"></div>
          <span>正在查询知识库...</span>
        </div>

        <!-- 限制提示（仅在非发送状态且真正达到限制时显示） -->
        <div v-if="!chatStore.canSend && !chatStore.sending && chatStore.turnCount >= 20" class="limit-warning">
          已达最大对话轮数限制（20 轮）
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="turn-info" v-if="chatStore.currentId">
          第 {{ chatStore.turnCount + 1 }}/20 轮 ·
          {{ formatTokens(chatStore.totalTokens) }}/128K token
        </div>
        <ChatInput
          :sending="chatStore.sending"
          :disabled="!chatStore.canSend"
          @send="handleSend"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useChatStore } from '../stores/chat.js'
import ChatMessage from '../components/chat/ChatMessage.vue'
import ChatInput from '../components/chat/ChatInput.vue'
import ConversationList from '../components/chat/ConversationList.vue'

const chatStore = useChatStore()
const flowRef = ref(null)

onMounted(() => {
  chatStore.loadConversations()
})

async function handleNew() {
  await chatStore.newConversation()
}

function handleSelect(id) {
  chatStore.selectConversation(id)
}

async function handleDelete(id) {
  await chatStore.deleteConversation(id)
}

async function handleClear() {
  if (confirm('确定清空所有对话？')) {
    await chatStore.clearConversations()
  }
}

async function handleSend(query) {
  if (!chatStore.currentId) {
    await chatStore.newConversation()
  }
  await chatStore.send(query)
  await nextTick()
  scrollToBottom()
}

function handleSourceClick(src) {
  console.log('Source clicked:', src)
}

function scrollToBottom() {
  if (flowRef.value) {
    flowRef.value.scrollTop = flowRef.value.scrollHeight
  }
}

function formatTokens(tokens) {
  if (!tokens) return '0'
  return (tokens / 1000).toFixed(1) + 'K'
}
</script>

<style scoped>
.workspace {
  display: flex;
  gap: var(--space-md);
  height: calc(100vh - 48px - 48px);
}

.history-sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  overflow-y: auto;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: var(--font-md);
  margin-bottom: var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--border-subtle);
}

.clear-btn {
  padding: 2px 8px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-disabled);
  cursor: pointer;
  font-size: var(--font-xs);
}

.clear-btn:hover {
  color: var(--text-secondary);
  border-color: var(--critical);
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  min-width: 0;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

.empty-state h2 {
  font-family: var(--font-display);
  font-size: var(--font-xl);
  color: var(--text-primary);
}

.empty-state ul {
  list-style: none;
  padding: 0;
  text-align: center;
}

.empty-state li {
  padding: 4px 0;
  font-size: var(--font-md);
}

.limit-note {
  margin-top: 16px;
  font-size: var(--font-xs);
  color: var(--text-disabled);
}

.message-flow {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md);
  background: var(--bg-canvas);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}

.limit-warning {
  text-align: center;
  padding: 12px;
  background: rgba(242, 73, 92, 0.1);
  color: var(--critical);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
}

.input-area {
  flex-shrink: 0;
}

.turn-info {
  text-align: right;
  font-size: var(--font-xs);
  color: var(--text-disabled);
  margin-bottom: 4px;
  padding-right: 4px;
}
/* 发送中提示 */
.sending-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px var(--space-md);
  color: var(--text-secondary);
  font-size: var(--font-sm);
}

.sending-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--info);
  animation: pulse-dot 1.2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}
</style>
