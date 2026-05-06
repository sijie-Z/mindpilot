<template>
  <div class="page">
    <header class="page-header">
      <div class="header-left">
        <h1>知识库管理</h1>
        <span class="header-count" v-if="filteredBases.length">{{ filteredBases.length }} 个知识库</span>
      </div>
      <div class="header-right">
        <div class="search-box">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input v-model="search" placeholder="搜索知识库..." />
        </div>
        <button class="btn-primary" @click="showCreate = true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          新建知识库
        </button>
      </div>
    </header>

    <main class="page-content">
      <!-- Loading -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>加载中...</p>
      </div>

      <!-- Empty -->
      <div v-else-if="filteredBases.length === 0 && !search" class="empty-state">
        <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-tertiary)" stroke-width="1">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
        </svg>
        <h2>暂无知识库</h2>
        <p>创建您的第一个知识库，开始构建智能检索系统</p>
        <button class="btn-primary" @click="showCreate = true">创建知识库</button>
      </div>

      <!-- Search empty -->
      <div v-else-if="filteredBases.length === 0" class="empty-state">
        <p>未找到匹配 "{{ search }}" 的知识库</p>
      </div>

      <!-- Grid -->
      <div v-else class="kb-grid">
        <div
          v-for="kb in filteredBases"
          :key="kb.id"
          class="kb-card"
          @click="$router.push(`/knowledge/${kb.id}`)"
        >
          <div class="card-top">
            <div class="card-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
              </svg>
            </div>
            <button class="card-delete" @click.stop="handleDelete(kb.id)" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
          <h3>{{ kb.name }}</h3>
          <p class="card-desc">{{ kb.description || '暂无描述' }}</p>
          <div class="card-meta">
            <span class="meta-item">
              <b>{{ kb.doc_count || 0 }}</b> 文档
            </span>
            <span class="meta-divider"></span>
            <span class="meta-item">
              <b>{{ kb.chunk_count || 0 }}</b> 片段
            </span>
          </div>
        </div>
      </div>
    </main>

    <!-- Create Modal -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal-panel">
        <div class="modal-header">
          <h2>创建知识库</h2>
          <button class="modal-close" @click="showCreate = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>名称 <span class="required">*</span></label>
            <input v-model="newKb.name" placeholder="输入知识库名称" @keyup.enter="handleCreate" />
          </div>
          <div class="form-group">
            <label>描述</label>
            <textarea v-model="newKb.description" placeholder="输入描述（可选）" rows="2"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showCreate = false">取消</button>
          <button class="btn-primary" @click="handleCreate" :disabled="!newKb.name.trim()">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/index'

interface KnowledgeBase { id: string; name: string; description?: string; doc_count?: number; chunk_count?: number }

const knowledgeBases = ref<KnowledgeBase[]>([])
const loading = ref(false)
const search = ref('')
const showCreate = ref(false)
const newKb = ref({ name: '', description: '' })

const filteredBases = computed(() => {
  if (!search.value) return knowledgeBases.value
  const q = search.value.toLowerCase()
  return knowledgeBases.value.filter(kb =>
    kb.name.toLowerCase().includes(q) ||
    (kb.description || '').toLowerCase().includes(q)
  )
})

onMounted(() => loadKnowledgeBases())

async function loadKnowledgeBases() {
  loading.value = true
  try {
    const res = await api.get('/knowledge/')
    knowledgeBases.value = Array.isArray(res.data) ? res.data : (res.data?.items || [])
  } catch { /* fallback */ }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!newKb.value.name.trim()) return
  try {
    await api.post('/knowledge/', newKb.value)
    ElMessage.success('创建成功')
    showCreate.value = false
    newKb.value = { name: '', description: '' }
    await loadKnowledgeBases()
  } catch { ElMessage.error('创建失败') }
}

async function handleDelete(id: string) {
  try {
    await api.delete(`/knowledge/${id}`)
    knowledgeBases.value = knowledgeBases.value.filter(k => k.id !== id)
    ElMessage.success('已删除')
  } catch { ElMessage.error('删除失败') }
}
</script>

<style scoped>
.page {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
}

/* ── Header ── */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-8);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.header-left { display: flex; align-items: baseline; gap: var(--space-3); }
.header-left h1 {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--color-text);
}
.header-count {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
}
.header-right { display: flex; align-items: center; gap: var(--space-4); }

.search-box {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  transition: border-color var(--transition-fast);
}
.search-box:focus-within { border-color: var(--color-primary); }
.search-box svg { color: var(--color-text-tertiary); flex-shrink: 0; }
.search-box input {
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-sm);
  color: var(--color-text);
  font-family: var(--font-sans);
  width: 200px;
}
.search-box input::placeholder { color: var(--color-text-tertiary); }

.btn-primary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: background var(--transition-fast);
  font-family: var(--font-sans);
}
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Content ── */
.page-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-8);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-16);
  gap: var(--space-4);
  color: var(--color-text-secondary);
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-16);
  text-align: center;
  gap: var(--space-3);
}
.empty-state h2 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--color-text);
}
.empty-state p {
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  margin-bottom: var(--space-4);
}

/* ── Grid ── */
.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-4);
}
.kb-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}
.kb-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}
.card-icon {
  width: 44px;
  height: 44px;
  background: var(--color-primary-light);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}
.card-delete {
  opacity: 0;
  display: flex;
  align-items: center;
  padding: var(--space-1);
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.kb-card:hover .card-delete { opacity: 1; }
.card-delete:hover { background: var(--color-error); color: #fff; }

.kb-card h3 {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-text);
  margin-bottom: var(--space-1);
}
.card-desc {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-normal);
  margin-bottom: var(--space-4);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}
.card-meta b {
  color: var(--color-primary);
  font-weight: var(--font-semibold);
}
.meta-divider {
  width: 1px;
  height: 12px;
  background: var(--color-border);
}

/* ── Modal ── */
.modal-overlay {
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
  width: 420px;
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
.modal-header h2 {
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
.modal-close:hover { background: var(--color-bg-tertiary); color: var(--color-text); }

.modal-body { padding: var(--space-5); }
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
}

.form-group { margin-bottom: var(--space-4); }
.form-group:last-child { margin-bottom: 0; }
.form-group label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
  margin-bottom: var(--space-2);
}
.required { color: var(--color-error); }
.form-group input, .form-group textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--color-text);
  font-family: var(--font-sans);
  transition: border-color var(--transition-fast);
  outline: none;
}
.form-group input:focus, .form-group textarea:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-light);
}
.form-group textarea { resize: vertical; }

.btn-secondary {
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  font-family: var(--font-sans);
  transition: all var(--transition-fast);
}
.btn-secondary:hover { background: var(--color-bg-tertiary); color: var(--color-text); }
</style>
