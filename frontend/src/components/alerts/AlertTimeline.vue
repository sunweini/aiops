<template>
  <div class="alert-timeline">
    <div v-for="alert in alerts" :key="alert.id" class="alert-item">
      <StatusBadge :status="alert.severity" />
      <div class="alert-content">
        <div class="alert-title">{{ alert.title }}</div>
        <div class="alert-meta">
          影响 {{ alert.affectedServices.length }} 个服务 · {{ formatTime(alert.timestamp) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import StatusBadge from '../common/StatusBadge.vue'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

defineProps({
  alerts: {
    type: Array,
    default: () => []
  }
})

const formatTime = (timestamp) => {
  return dayjs(timestamp).fromNow()
}
</script>

<style scoped>
.alert-timeline {
  max-height: 400px;
  overflow-y: auto;
}

.alert-item {
  padding: 12px;
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.alert-content {
  flex: 1;
}

.alert-title {
  font-size: var(--font-md);
  font-weight: 500;
  margin-bottom: 4px;
}

.alert-meta {
  font-size: var(--font-xs);
  color: var(--text-secondary);
}
</style>
