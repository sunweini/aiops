<template>
  <div class="app-layout">
    <TopNav />
    <Sidebar />
    <main class="main-content">
      <slot />
    </main>
  </div>
</template>

<script setup>
import TopNav from './TopNav.vue'
import Sidebar from './Sidebar.vue'
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
}

.main-content {
  margin-left: 200px;
  margin-top: 48px;
  padding: var(--space-lg);
}
</style>
