<template>
  <div class="modal" @click.self="$emit('close')">
    <div class="modal-panel">
      <div class="modal-header">
        <h3>搜索历史对话</h3>
        <button class="modal-close" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="search-input-wrapper">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索对话内容..."
            class="search-input"
            @keydown.enter="performSearch"
          />
        </div>
        <div v-if="loading" class="search-loading">搜索中...</div>
        <div v-else-if="results.length > 0" class="search-results">
          <div
            v-for="result in results"
            :key="result.session_id + result.content"
            class="search-result-item"
            @click="$emit('go-to-session', result.session_id)"
          >
            <div class="search-result-session">会话 {{ result.session_id?.slice(0, 8) }}...</div>
            <div class="search-result-content">{{ result.content }}</div>
            <div class="search-result-time">{{ formatTime(result.created_at) }}</div>
          </div>
        </div>
        <div v-else-if="searchQuery && !loading" class="search-empty">
          未找到匹配的对话内容
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import api from '@/api/index'

interface SearchResult {
  session_id: string
  content: string
  created_at: string
}

const emit = defineEmits<{
  close: []
  'go-to-session': [sessionId: string]
}>()

const searchQuery = ref('')
const results = ref<SearchResult[]>([])
const loading = ref(false)

async function performSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  loading.value = true
  try {
    const res = await api.get('/chat/search', { params: { q, limit: 20 } })
    results.value = res.data?.results || []
  } catch {
    results.value = []
  } finally {
    loading.value = false
  }
}

function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  backdrop-filter: blur(4px);
}
.modal-panel {
  width: 480px;
  max-height: 480px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border);
}
.modal-header h3 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}
.modal-close {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-tertiary);
  cursor: pointer;
}
.modal-close:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
}
.modal-body {
  padding: var(--space-4);
  max-height: 360px;
  overflow-y: auto;
}
.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}
.search-input-wrapper svg { color: var(--color-text-tertiary); flex-shrink: 0; }
.search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-sm);
  color: var(--color-text);
  font-family: var(--font-sans);
}
.search-input::placeholder { color: var(--color-text-tertiary); }
.search-loading {
  text-align: center;
  padding: var(--space-6);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
}
.search-results {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.search-result-item {
  padding: var(--space-3);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.search-result-item:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.search-result-session {
  font-size: var(--text-xs);
  color: var(--color-primary);
  font-weight: var(--font-medium);
  margin-bottom: var(--space-1);
}
.search-result-content {
  font-size: var(--text-sm);
  color: var(--color-text);
  line-height: var(--leading-normal);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.search-result-time {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: var(--space-1);
}
.search-empty {
  text-align: center;
  padding: var(--space-6);
  color: var(--color-text-tertiary);
  font-size: var(--text-sm);
}
</style>
