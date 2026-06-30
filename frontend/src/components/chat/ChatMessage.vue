<template>
  <div class="chat-message" :class="message.role">
    <div class="avatar">
      {{ message.role === 'user' ? '👤' : '🤖' }}
    </div>
    <div class="bubble">
      <div class="content" v-html="renderedContent"></div>
      <!-- 来源引用 -->
      <div v-if="message.sources && message.sources.length" class="sources">
        <div class="sources-label">来源</div>
        <span
          v-for="(src, i) in message.sources"
          :key="i"
          class="source-ref"
          @click="$emit('source-click', src)"
        >
          [{{ i + 1 }}] {{ src.title || src.id }}
        </span>
      </div>
      <!-- 置信度 -->
      <div v-if="message.confidence" class="confidence">
        置信度：<span :class="message.confidence">{{ confidenceLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true }
})

defineEmits(['source-click'])

// 简单 Markdown -> HTML 转换（支持代码块、粗体、列表）
const renderedContent = computed(() => {
  let html = props.message.content || ''

  // 代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang}">${escapeHtml(code.trim())}</code></pre>`
  )

  // 行内代码
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

  // 粗体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  // 换行
  html = html.replace(/\n/g, '<br>')

  return html
})

const confidenceLabel = computed(() => {
  const labels = { high: '🟢 高', medium: '🟡 中', low: '🔴 低' }
  return labels[props.message.confidence] || '🟡 中'
})

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}
</script>

<style scoped>
.chat-message {
  display: flex;
  gap: 12px;
  margin-bottom: var(--space-lg);
}

.chat-message.assistant {
  flex-direction: row;
}

.chat-message.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-elevated);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.bubble {
  max-width: 75%;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  font-size: var(--font-md);
  line-height: 1.7;
}

.user .bubble {
  background: var(--info);
  color: #fff;
  border-bottom-right-radius: var(--radius-sm);
}

.assistant .bubble {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-bottom-left-radius: var(--radius-sm);
}

.content :deep(pre) {
  background: var(--bg-elevated);
  padding: 12px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  font-family: var(--font-data);
  font-size: var(--font-xs);
  margin: 8px 0;
}

.content :deep(code) {
  background: var(--bg-elevated);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: var(--font-data);
  font-size: var(--font-xs);
}

.content :deep(pre code) {
  background: none;
  padding: 0;
}

.sources {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-subtle);
}

.sources-label {
  font-size: var(--font-xs);
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.source-ref {
  display: inline-block;
  font-size: var(--font-xs);
  color: var(--info);
  cursor: pointer;
  margin-right: 12px;
}

.source-ref:hover {
  text-decoration: underline;
}

.confidence {
  margin-top: 4px;
  font-size: var(--font-xs);
  color: var(--text-secondary);
}

.confidence :deep(.high) { color: var(--healthy); }
.confidence :deep(.medium) { color: var(--warning); }
.confidence :deep(.low) { color: var(--critical); }
</style>
