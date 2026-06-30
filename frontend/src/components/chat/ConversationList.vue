<template>
  <div class="conversation-list">
    <button class="new-btn" @click="$emit('new')">
      + 新对话
    </button>
    <div
      v-for="conv in conversations"
      :key="conv.conversation_id"
      class="conv-item"
      :class="{ active: conv.conversation_id === activeId }"
      @click="$emit('select', conv.conversation_id)"
    >
      <div class="conv-title">{{ conv.title }}</div>
      <div class="conv-meta">
        {{ conv.turn_count }} 轮 · {{ formatTime(conv.created_at) }}
      </div>
    </div>
  </div>
</template>

<script setup>
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: String, default: null }
})

defineEmits(['new', 'select'])

const formatTime = (ts) => dayjs(ts).fromNow()
</script>

<style scoped>
.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.new-btn {
  padding: 10px;
  background: var(--info);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: var(--font-md);
  font-weight: 500;
  margin-bottom: 8px;
}

.new-btn:hover {
  filter: brightness(1.1);
}

.conv-item {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s;
}

.conv-item:hover {
  background: var(--bg-elevated);
}

.conv-item.active {
  background: var(--bg-elevated);
  border-left: 3px solid var(--info);
}

.conv-title {
  font-size: var(--font-sm);
  font-weight: 500;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-meta {
  font-size: var(--font-xs);
  color: var(--text-secondary);
}
</style>
