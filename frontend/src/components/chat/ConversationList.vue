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
    >
      <div class="conv-main" @click="$emit('select', conv.conversation_id)">
        <div class="conv-title">{{ conv.title }}</div>
        <div class="conv-meta">
          {{ conv.turn_count }} 轮 · {{ formatTime(conv.created_at) }}
        </div>
      </div>
      <button class="delete-btn" @click.stop="$emit('delete', conv.conversation_id)" title="删除对话">✕</button>
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

defineEmits(['new', 'select', 'delete'])

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
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
  transition: background 0.15s;
}

.conv-item:hover {
  background: var(--bg-elevated);
}

.conv-item.active {
  background: var(--bg-elevated);
  border-left: 3px solid var(--info);
}

.conv-main {
  flex: 1;
  padding: 10px 12px;
  cursor: pointer;
  min-width: 0;
}

.delete-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  margin-right: 8px;
  background: transparent;
  border: none;
  color: var(--text-disabled);
  cursor: pointer;
  border-radius: var(--radius-sm);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s;
}

.conv-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: var(--critical);
  background: rgba(242, 73, 92, 0.1);
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
