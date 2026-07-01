<template>
  <AppLayout>
    <router-view />
  </AppLayout>
</template>

<script setup>
import AppLayout from './components/layout/AppLayout.vue'
</script>

<style>
body {
  margin: 0;
  background: #0a0e1a;
  color: rgba(255, 255, 255, 0.87);
  font-family: 'DM Sans', sans-serif;
}
</style>
