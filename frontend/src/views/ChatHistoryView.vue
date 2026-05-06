<template>
  <div class="page">
    <header class="page-header">
      <button class="back-btn" @click="$router.push('/chat')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
        返回
      </button>
      <h1>对话历史</h1>
      <div class="search-box">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input v-model="search" placeholder="搜索对话..." />
      </div>
    </header>

    <main class="page-content">
      <div v-if="filtered.length === 0" class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-tertiary)" stroke-width="1">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        <p>{{ search ? '未找到匹配的对话' : '暂无历史记录' }}</p>
        <button v-if="!search" class="btn-primary" @click="$router.push('/chat')">开始对话</button>
      </div>

      <div v-else class="history-list">
        <div
          v-for="s in filtered"
          :key="s.id"
          class="history-item"
          @click="openSession(s.id)"
        >
          <div class="item-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div class="item-info">
            <h3>{{ s.title || '未命名对话' }}</h3>
            <p>{{ s.preview || '暂无预览' }}</p>
            <div class="item-meta">
              <span>{{ s.count || 0 }} 条消息</span>
              <span class="meta-dot"></span>
              <span>{{ formatDate(s.time || s.updated_at) }}</span>
            </div>
          </div>
          <button class="item-delete" @click.stop="handleDelete(s.id)" title="删除">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const chatStore = useChatStore()
const search = ref('')

interface LocalSession { id: string; title?: string; preview?: string; count?: number; time?: number; updated_at?: string }

const filtered = computed(() => {
  // Merge backend sessions with localStorage
  const all: LocalSession[] = [...chatStore.sessions.map(s => ({
    id: s.id,
    title: s.title,
    preview: s.messages?.[s.messages.length - 1]?.content?.slice(0, 60),
    count: s.messages?.length,
    time: s.updated_at ? new Date(s.updated_at).getTime() : 0,
  }))]

  // Add localStorage cache
  try {
    const cached = JSON.parse(localStorage.getItem('mindpilot_chat_sessions') || '[]')
    for (const item of cached) {
      if (!all.find(a => a.id === item.id)) {
        all.push({
          id: item.id,
          title: item.title,
          preview: item.messages?.[item.messages.length - 1]?.content?.slice(0, 60),
          count: item.messages?.length,
          time: item.updated_at ? new Date(item.updated_at).getTime() : 0,
        })
      }
    }
  } catch { /* ignore */ }

  all.sort((a, b) => (b.time || 0) - (a.time || 0))

  if (!search.value) return all
  const q = search.value.toLowerCase()
  return all.filter(s =>
    (s.title || '').toLowerCase().includes(q) ||
    (s.preview || '').toLowerCase().includes(q)
  )
})

onMounted(() => {
  chatStore.initialize()
})

function openSession(id: string) {
  router.push(`/chat?session=${id}`)
}

async function handleDelete(id: string) {
  await chatStore.deleteSession(id)
  ElMessage.success('已删除')
}

function formatDate(tsOrStr: number | string | undefined) {
  if (!tsOrStr) return ''
  const d = typeof tsOrStr === 'number' ? new Date(tsOrStr) : new Date(tsOrStr)
  if (isNaN(d.getTime())) return ''
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 86400000)
  if (diff === 0) return '今天'
  if (diff === 1) return '昨天'
  if (diff < 7) return `${diff}天前`
  return d.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.page { height: 100%; display: flex; flex-direction: column; background: var(--color-bg); }

.page-header {
  display: flex; align-items: center; gap: var(--space-4);
  padding: var(--space-5) var(--space-8);
  background: var(--color-surface); border-bottom: 1px solid var(--color-border);
}
.page-header h1 { font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--color-text); }

.back-btn {
  display: flex; align-items: center; gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg); border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); color: var(--color-text-secondary);
  font-size: var(--text-sm); cursor: pointer; font-family: var(--font-sans);
  transition: all var(--transition-fast);
}
.back-btn:hover { background: var(--color-bg-tertiary); color: var(--color-text); }

.search-box {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--color-bg); border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); margin-left: auto;
  transition: border-color var(--transition-fast);
}
.search-box:focus-within { border-color: var(--color-primary); }
.search-box svg { color: var(--color-text-tertiary); }
.search-box input {
  border: none; outline: none; background: transparent;
  font-size: var(--text-sm); color: var(--color-text); font-family: var(--font-sans);
  width: 180px;
}
.search-box input::placeholder { color: var(--color-text-tertiary); }

.btn-primary {
  padding: var(--space-2) var(--space-5);
  background: var(--color-primary); border: none; border-radius: var(--radius-md);
  color: #fff; font-size: var(--text-sm); font-weight: var(--font-medium);
  cursor: pointer; font-family: var(--font-sans); transition: background var(--transition-fast);
}
.btn-primary:hover { background: var(--color-primary-hover); }

.page-content { flex: 1; overflow-y: auto; padding: var(--space-6) var(--space-8); }

.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: var(--space-16); gap: var(--space-3); color: var(--color-text-secondary);
}

.history-list { max-width: 680px; margin: 0 auto; display: flex; flex-direction: column; gap: var(--space-3); }

.history-item {
  display: flex; align-items: center; gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-lg); cursor: pointer; transition: all var(--transition-fast);
}
.history-item:hover { border-color: var(--color-primary); box-shadow: var(--shadow-sm); }

.item-icon {
  width: 40px; height: 40px; background: var(--color-primary-light);
  border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.item-info { flex: 1; min-width: 0; }
.item-info h3 { font-size: var(--text-sm); font-weight: var(--font-medium); color: var(--color-text); margin-bottom: 2px; }
.item-info p { font-size: var(--text-xs); color: var(--color-text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-bottom: var(--space-1); }
.item-meta { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-xs); color: var(--color-text-tertiary); }
.meta-dot { width: 3px; height: 3px; border-radius: 50%; background: var(--color-text-tertiary); }
.item-delete {
  opacity: 0; display: flex; padding: var(--space-1); background: none; border: none;
  border-radius: var(--radius-sm); color: var(--color-text-tertiary); cursor: pointer;
  transition: all var(--transition-fast);
}
.history-item:hover .item-delete { opacity: 1; }
.item-delete:hover { background: var(--color-error); color: #fff; }
</style>
