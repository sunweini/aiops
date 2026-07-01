<template>
  <span class="badge" :class="status">
    <span class="badge-dot"></span>
    <span class="badge-icon">{{ icon }}</span>
    <span class="badge-text">{{ label }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    required: true,
    validator: (v) => ['critical', 'warning', 'healthy', 'info', 'unknown'].includes(v)
  }
})

const icon = computed(() => {
  const icons = {
    critical: '⚠',
    warning: '⚡',
    healthy: '✓',
    info: 'ℹ',
    unknown: '?'
  }
  return icons[props.status] || '?'
})

const label = computed(() => {
  const labels = {
    critical: '严重故障',
    warning: '性能告警',
    healthy: '运行正常',
    info: '信息',
    unknown: '未知'
  }
  return labels[props.status] || '未知'
})
</script>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: 500;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.badge.critical {
  background: rgba(242, 73, 92, 0.15);
  color: var(--critical);
}

.badge.warning {
  background: rgba(250, 222, 42, 0.15);
  color: var(--warning);
}

.badge.healthy {
  background: rgba(115, 191, 105, 0.15);
  color: var(--healthy);
}

.badge.info {
  background: rgba(87, 148, 242, 0.15);
  color: var(--info);
}

.badge.unknown {
  background: rgba(142, 142, 142, 0.15);
  color: var(--unknown);
}
</style>
