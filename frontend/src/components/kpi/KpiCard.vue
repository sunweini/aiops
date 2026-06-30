<template>
  <div class="kpi-card">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value" :class="status">{{ value }}</div>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: [String, Number],
  status: {
    type: String,
    default: 'healthy',
    validator: (v) => ['healthy', 'warning', 'critical'].includes(v)
  }
})
</script>

<style scoped>
.kpi-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
}

.kpi-label {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-xs);
}

.kpi-value {
  font-family: var(--font-data);
  font-size: var(--font-2xl);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.kpi-value.healthy { color: var(--healthy); }
.kpi-value.warning { color: var(--warning); }
.kpi-value.critical { color: var(--critical); }
</style>
