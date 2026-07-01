import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/Dashboard.vue')
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('../views/Workspace.vue')
  },
  {
    path: '/hosts',
    name: 'HostList',
    component: () => import('../views/HostList.vue')
  },
  {
    path: '/hosts/:host_id',
    name: 'HostDetail',
    component: () => import('../views/HostDetail.vue')
  },
  {
    path: '/alerts',
    name: 'Alerts',
    component: () => import('../views/Alerts.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
