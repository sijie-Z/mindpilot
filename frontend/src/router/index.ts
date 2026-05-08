import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/login', name: 'Login', component: () => import('@/views/LoginView.vue'), meta: { requiresAuth: false } },
    { path: '/chat', name: 'Chat', component: () => import('@/views/ChatView.vue'), meta: { requiresAuth: true } },
    { path: '/chat/history', name: 'ChatHistory', component: () => import('@/views/ChatHistoryView.vue'), meta: { requiresAuth: true } },
    { path: '/knowledge', name: 'Knowledge', component: () => import('@/views/KnowledgeView.vue'), meta: { requiresAuth: true } },
    { path: '/knowledge/:id', name: 'KnowledgeDetail', component: () => import('@/views/KnowledgeDetailView.vue'), props: true, meta: { requiresAuth: true } },
    { path: '/workflow', name: 'Workflow', component: () => import('@/views/WorkflowView.vue'), meta: { requiresAuth: true } },
    { path: '/admin', name: 'Admin', component: () => import('@/views/AdminView.vue'), meta: { requiresAuth: true } },
    { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFoundView.vue') },
  ],
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth !== false && !token) next('/login')
  else if (to.path === '/login' && token) next('/chat')
  else next()
})

// Listen for auth logout events from API interceptor
window.addEventListener('auth:logout', () => {
  router.push('/login')
})

export default router
