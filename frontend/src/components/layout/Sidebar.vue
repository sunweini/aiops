<template>
  <aside class="sidebar">
    <router-link to="/dashboard" class="nav-item" active-class="active">
      📊 全局看板
    </router-link>
    <router-link to="/workspace" class="nav-item" active-class="active">
      💻 工作台
    </router-link>
    <router-link to="/hosts" class="nav-item" active-class="active">
      🖥 主机监控
    </router-link>
    <router-link to="/alerts" class="nav-item" active-class="active">
      🔔 告警中心
    </router-link>
  </aside>
</template>

<script setup>
</script>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 48px;
  width: 200px;
  height: calc(100vh - 48px);
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  padding: var(--space-md) 0;
}

.nav-item {
  display: block;
  padding: 10px var(--space-md);
  color: var(--text-secondary);
  font-size: var(--font-md);
  text-decoration: none;
  transition: all 0.2s;
}

.nav-item:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--bg-elevated);
  color: var(--info);
  border-left: 3px solid var(--info);
}
</style>
