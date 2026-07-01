<template>
  <nav class="top-nav">
    <div class="logo">AIOps 运维平台</div>
    <input class="search-bar" placeholder="全局搜索... (⌘K)" readonly>
    <div class="user-info">管理员</div>
  </nav>
</template>

<script setup>
</script>

<style scoped>
.top-nav {
  height: 48px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  align-items: center;
  padding: 0 var(--space-md);
  gap: var(--space-md);
}

.logo {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: var(--font-lg);
  color: var(--info);
}

.search-bar {
  flex: 1;
  max-width: 400px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 6px 12px;
  color: var(--text-secondary);
  font-size: var(--font-sm);
}

.user-info {
  font-size: var(--font-sm);
  color: var(--text-secondary);
}
</style>
