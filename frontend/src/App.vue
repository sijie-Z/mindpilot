<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': appStore.sidebarCollapsed }">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <router-link to="/chat" class="logo">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
          <span class="logo-text">MindPilot</span>
        </router-link>
        <button class="sidebar-toggle" @click="appStore.toggleSidebar()" title="折叠侧边栏">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
        </button>
      </div>

      <button class="new-chat-btn" @click="startNewChat">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        <span>新对话</span>
      </button>

      <div class="search-box">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input v-model="searchQuery" placeholder="搜索对话..." />
      </div>

      <div class="session-list">
        <div class="list-label">最近对话</div>
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: chatStore.currentSessionId === session.id }"
          @click="selectSession(session.id)"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
          <span class="session-title">{{ session.title || '新对话' }}</span>
          <button
            class="session-delete"
            @click.stop="handleDeleteSession(session.id)"
            title="删除"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>

        <div v-if="chatStore.sessions.length === 0" class="empty-sessions">
          <p>暂无对话记录</p>
        </div>
      </div>

      <div class="sidebar-footer">
        <nav class="sidebar-nav">
          <router-link to="/knowledge" class="nav-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            </svg>
            <span>知识库</span>
          </router-link>
          <router-link to="/workflow" class="nav-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>
            </svg>
            <span>工作流</span>
          </router-link>
          <router-link to="/admin" class="nav-item">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
            </svg>
            <span>设置</span>
          </router-link>
        </nav>

        <div class="sidebar-bottom">
          <div class="status-row">
            <span
              class="health-dot"
              :class="{ online: appStore.backendOnline }"
              :title="appStore.backendOnline ? '后端在线' : '后端离线'"
            ></span>
            <span class="health-text">{{ appStore.backendOnline ? '服务在线' : '服务离线' }}</span>
          </div>

          <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '切换亮色模式' : '切换暗色模式'">
            <svg v-if="!isDark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
          </button>

          <div class="user-info">
            <div class="user-avatar">{{ username.charAt(0).toUpperCase() }}</div>
            <span class="user-name">{{ username }}</span>
            <button class="logout-btn" @click="handleLogout" title="退出登录">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const appStore = useAppStore()
const chatStore = useChatStore()

const searchQuery = ref('')

const username = computed(() => localStorage.getItem('username') || 'User')
const isDark = computed(() => appStore.isDarkMode)

const filteredSessions = computed(() => {
  if (!searchQuery.value) return chatStore.sessions.slice(0, 20)
  const q = searchQuery.value.toLowerCase()
  return chatStore.sessions.filter(s =>
    (s.title || '').toLowerCase().includes(q)
  )
})

onMounted(() => {
  appStore.initialize()
  chatStore.initialize()
})

function startNewChat() {
  chatStore.startNewSession()
  router.push('/chat')
}

function selectSession(id: string) {
  chatStore.loadSession(id)
  router.push(`/chat?session=${id}`)
}

async function handleDeleteSession(id: string) {
  await chatStore.deleteSession(id)
}

function toggleTheme() {
  const next = isDark.value ? 'light' : 'dark'
  appStore.setTheme(next)
}

function handleLogout() {
  localStorage.clear()
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  background: var(--color-bg);
}

/* ── Sidebar ── */
.sidebar {
  width: var(--sidebar-width);
  background: var(--color-surface);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--transition-normal);
}

.sidebar-collapsed .sidebar {
  width: 64px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-4);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
}
.logo-text {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--color-text);
}
.sidebar-collapsed .logo-text { display: none; }

.sidebar-toggle {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.sidebar-toggle:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}
.sidebar-collapsed .sidebar-toggle {
  display: none;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  margin: 0 var(--space-3) var(--space-3);
  padding: var(--space-2) var(--space-4);
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: background var(--transition-fast);
}
.new-chat-btn:hover { background: var(--color-primary-hover); }
.sidebar-collapsed .new-chat-btn span { display: none; }
.sidebar-collapsed .new-chat-btn {
  margin: 0 var(--space-2) var(--space-2);
  padding: var(--space-2);
}

.search-box {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 var(--space-3) var(--space-3);
  padding: var(--space-1) var(--space-3);
  background: var(--color-bg-tertiary);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  transition: border-color var(--transition-fast);
}
.search-box:focus-within {
  border-color: var(--color-primary);
  background: var(--color-bg);
}
.search-box svg {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.search-box input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: var(--text-sm);
  color: var(--color-text);
  outline: none;
  padding: var(--space-2) 0;
}
.search-box input::placeholder { color: var(--color-text-tertiary); }
.sidebar-collapsed .search-box { display: none; }

/* ── Session List ── */
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--space-2);
}
.list-label {
  padding: var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  font-weight: var(--font-medium);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.sidebar-collapsed .list-label { display: none; }

.session-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--color-text);
  transition: background var(--transition-fast);
  position: relative;
}
.session-item:hover { background: var(--color-surface-hover); }
.session-item.active { background: var(--color-primary-light); }
.session-item svg {
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}
.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sidebar-collapsed .session-title { display: none; }

.session-delete {
  opacity: 0;
  display: flex;
  align-items: center;
  background: none;
  border: none;
  color: var(--color-text-tertiary);
  cursor: pointer;
  padding: var(--space-1);
  border-radius: var(--radius-sm);
}
.session-item:hover .session-delete { opacity: 1; }
.session-delete:hover {
  background: var(--color-error);
  color: #fff;
}
.sidebar-collapsed .session-delete { display: none; }

.empty-sessions {
  padding: var(--space-8) var(--space-4);
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
}

/* ── Sidebar Footer ── */
.sidebar-footer {
  border-top: 1px solid var(--color-border);
  padding: var(--space-2);
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: var(--text-sm);
  transition: all var(--transition-fast);
}
.nav-item:hover {
  background: var(--color-surface-hover);
  color: var(--color-text);
}
.nav-item.router-link-active {
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-weight: var(--font-medium);
}
.nav-item svg { flex-shrink: 0; }
.sidebar-collapsed .nav-item span { display: none; }
.sidebar-collapsed .nav-item {
  justify-content: center;
  padding: var(--space-3);
}

.sidebar-bottom {
  border-top: 1px solid var(--color-border-light);
  padding: var(--space-2) var(--space-1) 0;
  margin-top: var(--space-2);
}

.status-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
}
.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-error);
  flex-shrink: 0;
}
.health-dot.online {
  background: var(--color-success);
}
.health-text {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}
.sidebar-collapsed .health-text { display: none; }

.theme-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.theme-toggle:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}
.sidebar-collapsed .theme-toggle {
  justify-content: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2);
}
.user-avatar {
  width: 28px;
  height: 28px;
  background: var(--color-primary);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  flex-shrink: 0;
}
.user-name {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.logout-btn {
  display: flex;
  align-items: center;
  padding: var(--space-1);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.logout-btn:hover {
  background: var(--color-error);
  border-color: var(--color-error);
  color: #fff;
}
.sidebar-collapsed .user-name,
.sidebar-collapsed .logout-btn { display: none; }

/* ── Main Content ── */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg);
}
</style>
