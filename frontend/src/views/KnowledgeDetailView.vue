<template>
  <div class="page">
    <header class="page-header">
      <div class="header-left">
        <button class="back-btn" @click="$router.push('/knowledge')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          返回
        </button>
        <div class="header-info">
          <h1>{{ kb?.name || '加载中...' }}</h1>
          <p v-if="kb?.description">{{ kb.description }}</p>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn-secondary" @click="showRetrievalTest = true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          检索测试
        </button>
        <button class="btn-primary" @click="showUpload = true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
          </svg>
          上传文档
        </button>
      </div>
    </header>

    <!-- Stats Bar -->
    <div class="stats-bar">
      <div class="stat">
        <span class="stat-value">{{ documents.length }}</span>
        <span class="stat-label">文档</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ completedCount }}</span>
        <span class="stat-label">已完成</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ totalChunks }}</span>
        <span class="stat-label">片段</span>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button :class="{ active: tab === 'docs' }" @click="tab = 'docs'">文档列表</button>
      <button :class="{ active: tab === 'chunks' }" @click="tab = 'chunks'">文档片段</button>
      <button :class="{ active: tab === 'stats' }" @click="tab = 'stats'">统计信息</button>
    </div>

    <main class="page-content">
      <!-- Loading -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
      </div>

      <!-- Documents Tab -->
      <template v-else-if="tab === 'docs'">
        <div v-if="documents.length === 0" class="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-tertiary)" stroke-width="1">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
          </svg>
          <p>暂无文档</p>
          <button class="btn-primary" @click="showUpload = true">上传文档</button>
        </div>
        <div v-else>
          <!-- Batch actions bar -->
          <div class="batch-bar">
            <label class="batch-select-all">
              <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" />
              <span>全选</span>
            </label>
            <div v-if="selectedDocs.length > 0" class="batch-actions">
              <span class="batch-count">已选 {{ selectedDocs.length }} 项</span>
              <button class="btn-danger-sm" @click="handleBatchDelete">批量删除</button>
            </div>
          </div>
          <div class="doc-list">
            <div v-for="doc in documents" :key="doc.id" class="doc-item">
              <input type="checkbox" :checked="selectedDocs.includes(doc.id)" @change="toggleSelect(doc.id)" class="doc-checkbox" />
              <div class="doc-icon">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                </svg>
              </div>
              <div class="doc-info">
                <span class="doc-name">{{ doc.filename || doc.name }}</span>
                <span class="doc-meta">{{ formatSize(doc.file_size) }} · {{ doc.chunks || doc.chunk_count || 0 }} 片段</span>
                <!-- Tags -->
                <div class="doc-tags">
                  <span v-for="tag in (doc.tags || [])" :key="tag" class="tag-chip">
                    {{ tag }}
                    <button class="tag-remove" @click.stop="removeTag(doc.id, tag)">&times;</button>
                  </span>
                  <button class="tag-add-btn" @click="startAddTag(doc.id)" title="添加标签">+</button>
                </div>
              </div>
              <span class="doc-status" :class="doc.status">{{ statusLabel(doc.status) }}</span>
              <button class="doc-action" @click="handleDeleteDoc(doc.id)" title="删除">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
            <!-- Progress bar for processing documents (rendered below list) -->
            <div v-for="doc in documents.filter(d => d.status === 'processing')" :key="'progress-' + doc.id" class="doc-progress">
              <span class="progress-label">{{ doc.filename }}:</span>
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: (doc.progress || 0) + '%' }"></div>
              </div>
              <span class="progress-text">{{ doc.progress_detail || '处理中...' }} {{ doc.progress || 0 }}%</span>
            </div>
          </div>
        </div>
      </template>

      <!-- Chunks Tab -->
      <template v-else-if="tab === 'chunks'">
        <div class="chunk-search">
          <input v-model="chunkSearch" placeholder="搜索片段内容..." @keyup.enter="searchChunks" />
          <button class="btn-primary" @click="searchChunks">搜索</button>
        </div>
        <div v-if="chunkResults.length > 0" class="chunk-list">
          <div v-for="chunk in chunkResults" :key="chunk.id" class="chunk-item">
            <div class="chunk-header">
              <span class="chunk-idx">#{{ chunk.chunk_index + 1 }}</span>
              <span class="chunk-source">{{ chunk.metadata?.filename || '未知文档' }}</span>
            </div>
            <div class="chunk-text">{{ chunk.content?.slice(0, 300) }}{{ chunk.content?.length > 300 ? '...' : '' }}</div>
          </div>
        </div>
        <div v-else-if="chunkSearch" class="empty-state">
          <p>输入关键词搜索片段</p>
        </div>
        <div v-else class="empty-state">
          <p>在上方输入内容搜索文档片段</p>
        </div>
      </template>

      <!-- Stats Tab -->
      <template v-else-if="tab === 'stats'">
        <div class="stats-grid">
          <div class="stat-card">
            <h3>文档统计</h3>
            <div class="stat-row"><span>总文档数</span><b>{{ documents.length }}</b></div>
            <div class="stat-row"><span>已完成</span><b>{{ completedCount }}</b></div>
            <div class="stat-row"><span>处理中</span><b>{{ documents.filter(d => d.status === 'processing').length }}</b></div>
            <div class="stat-row"><span>失败</span><b>{{ documents.filter(d => d.status === 'failed').length }}</b></div>
          </div>
          <div class="stat-card">
            <h3>片段统计</h3>
            <div class="stat-row"><span>总片段数</span><b>{{ totalChunks }}</b></div>
            <div class="stat-row"><span>平均/文档</span><b>{{ documents.length ? (totalChunks / documents.length).toFixed(1) : 0 }}</b></div>
          </div>
          <div class="stat-card">
            <h3>存储统计</h3>
            <div class="stat-row"><span>总大小</span><b>{{ formatSize(totalSize) }}</b></div>
            <div class="stat-row"><span>平均文档</span><b>{{ formatSize(avgSize) }}</b></div>
          </div>
        </div>
      </template>
    </main>

    <!-- Upload Modal -->
    <div v-if="showUpload" class="modal-overlay" @click.self="showUpload = false">
      <div class="modal-panel">
        <div class="modal-header">
          <h2>上传文档</h2>
          <button class="modal-close" @click="showUpload = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="upload-zone" @click="fileInput?.click()">
            <input ref="fileInput" type="file" hidden multiple accept=".pdf,.docx,.doc,.pptx,.txt,.md" @change="handleFiles" />
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--color-text-tertiary)" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
            </svg>
            <p>点击选择文件上传</p>
            <p class="hint">支持 PDF、Word、PPT、TXT、Markdown</p>
          </div>
          <div v-if="uploading" class="upload-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <span>{{ uploadProgress }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Retrieval Test Modal -->
    <div v-if="showRetrievalTest" class="modal-overlay" @click.self="showRetrievalTest = false">
      <div class="modal-panel modal-lg">
        <div class="modal-header">
          <h2>检索测试</h2>
          <button class="modal-close" @click="showRetrievalTest = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="test-input-row">
            <input v-model="testQuery" placeholder="输入测试查询..." @keyup.enter="runRetrievalTest" />
            <button class="btn-primary" @click="runRetrievalTest" :disabled="testing">测试</button>
          </div>
          <div class="test-options">
            <label>Top K <input type="number" v-model.number="testTopK" min="1" max="20" /></label>
            <label>向量权重 <input type="range" v-model.number="testWeight" min="0" max="1" step="0.1" /> {{ testWeight }}</label>
          </div>
          <div v-if="testing" class="loading-state"><div class="spinner"></div></div>
          <div v-else-if="testResults.length > 0" class="test-results">
            <h4>{{ testResults.length }} 条结果</h4>
            <div v-for="(r, i) in testResults" :key="i" class="result-item">
              <div class="result-header">
                <span class="result-score">相关度 {{ (r.score * 100).toFixed(1) }}%</span>
                <span class="result-file">{{ r.metadata?.filename || '未知' }}</span>
              </div>
              <div class="result-content">
                <HighlightedText
                  :text="r.content || ''"
                  :sentences="r.sentence_scores"
                  :top-sentences="r.highlighted_sentences"
                  :threshold="0.3"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tag Input Modal -->
    <div v-if="showTagInput" class="modal-overlay" @click.self="showTagInput = false">
      <div class="modal-panel modal-sm">
        <div class="modal-header">
          <h2>添加标签</h2>
          <button class="modal-close" @click="showTagInput = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <input v-model="newTag" placeholder="输入标签名称..." @keyup.enter="confirmAddTag" class="tag-input" />
          <div class="tag-suggestions">
            <span v-for="t in commonTags" :key="t" class="tag-suggestion" @click="newTag = t">{{ t }}</span>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary" @click="showTagInput = false">取消</button>
          <button class="btn-primary" @click="confirmAddTag">添加</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import HighlightedText from '@/components/HighlightedText.vue'
import api from '@/api/index'

const route = useRoute()
const kbId = route.params.id as string

const kb = ref<any>(null)
const documents = ref<any[]>([])
const loading = ref(false)
const tab = ref('docs')
const showUpload = ref(false)
const showRetrievalTest = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const fileInput = ref<HTMLInputElement>()

// Batch operations
const selectedDocs = ref<string[]>([])
const allSelected = computed(() => documents.value.length > 0 && selectedDocs.value.length === documents.value.length)

function toggleSelect(docId: string) {
  const idx = selectedDocs.value.indexOf(docId)
  if (idx >= 0) selectedDocs.value.splice(idx, 1)
  else selectedDocs.value.push(docId)
}

function toggleSelectAll() {
  if (allSelected.value) selectedDocs.value = []
  else selectedDocs.value = documents.value.map(d => d.id)
}

async function handleBatchDelete() {
  if (selectedDocs.value.length === 0) return
  if (!confirm(`确定删除选中的 ${selectedDocs.value.length} 个文档？`)) return
  try {
    await api.post('/document/batch-delete', { doc_ids: selectedDocs.value })
    documents.value = documents.value.filter(d => !selectedDocs.value.includes(d.id))
    selectedDocs.value = []
    ElMessage.success('批量删除成功')
  } catch { ElMessage.error('批量删除失败') }
}

// Tag management
const showTagInput = ref(false)
const newTag = ref('')
const tagTargetDocId = ref('')
const commonTags = ['重要', '待审核', '已归档', '参考', '技术', '业务']

function startAddTag(docId: string) {
  tagTargetDocId.value = docId
  newTag.value = ''
  showTagInput.value = true
}

async function confirmAddTag() {
  if (!newTag.value.trim()) return
  const docId = tagTargetDocId.value
  const doc = documents.value.find(d => d.id === docId)
  if (!doc) return
  const tags = [...(doc.tags || []), newTag.value.trim()]
  try {
    await api.put(`/document/${docId}/tags`, { tags })
    doc.tags = tags
    showTagInput.value = false
    ElMessage.success('标签已添加')
  } catch { ElMessage.error('添加标签失败') }
}

async function removeTag(docId: string, tag: string) {
  const doc = documents.value.find(d => d.id === docId)
  if (!doc) return
  const tags = (doc.tags || []).filter((t: string) => t !== tag)
  try {
    await api.put(`/document/${docId}/tags`, { tags })
    doc.tags = tags
  } catch { ElMessage.error('删除标签失败') }
}

const chunkSearch = ref('')
const chunkResults = ref<any[]>([])
const testQuery = ref('')
const testTopK = ref(5)
const testWeight = ref(0.7)
const testing = ref(false)
const testResults = ref<any[]>([])

const totalChunks = computed(() => documents.value.reduce((s, d) => s + (d.chunks || d.chunk_count || 0), 0))
const completedCount = computed(() => documents.value.filter(d => d.status === 'done' || d.status === 'completed').length)
const totalSize = computed(() => documents.value.reduce((s, d) => s + (d.file_size || 0), 0))
const avgSize = computed(() => documents.value.length ? totalSize.value / documents.value.length : 0)

onMounted(() => loadData())

async function loadData() {
  loading.value = true
  try {
    const [kbRes, docRes] = await Promise.all([
      api.get(`/knowledge/${kbId}`),
      api.get(`/knowledge/${kbId}/documents`),
    ])
    kb.value = kbRes.data
    documents.value = docRes.data?.documents || docRes.data || []
  } catch (err) {
    console.error('Failed to load knowledge base data:', err)
    ElMessage.error('加载知识库数据失败')
  }
  finally { loading.value = false }
}

async function searchChunks() {
  if (!chunkSearch.value.trim()) return
  try {
    const res = await api.get(`/knowledge/${kbId}/search`, { params: { q: chunkSearch.value, limit: 20 } })
    chunkResults.value = res.data || []
  } catch { ElMessage.error('搜索失败') }
}

async function runRetrievalTest() {
  if (!testQuery.value.trim()) return
  testing.value = true
  try {
    const res = await api.post('/knowledge/search', {
      query: testQuery.value,
      knowledge_id: kbId,
      top_k: testTopK.value,
      vector_weight: testWeight.value,
    })
    const results = res.data?.results || res.data || []

    // Apply semantic highlighting to results
    try {
      const highlightRes = await api.post('/highlight/chunks', results, {
        params: { query: testQuery.value, top_k: 3 },
      })
      testResults.value = highlightRes.data?.chunks || results
    } catch {
      // Highlighting failed, use original results
      testResults.value = results
    }
  } catch { ElMessage.error('检索失败') }
  finally { testing.value = false }
}

async function handleDeleteDoc(id: string) {
  try {
    await api.delete(`/document/${id}`)
    documents.value = documents.value.filter(d => d.id !== id)
    ElMessage.success('已删除')
  } catch { ElMessage.error('删除失败') }
}

function handleFiles(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (files) uploadFiles(Array.from(files))
}

async function uploadFiles(files: File[]) {
  uploading.value = true
  uploadProgress.value = 0
  try {
    for (let i = 0; i < files.length; i++) {
      const form = new FormData()
      form.append('file', files[i])
      form.append('knowledge_id', kbId)
      await api.post('/document/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e: any) => {
          uploadProgress.value = Math.round(((i + e.loaded / e.total!) / files.length) * 100)
        },
      })
    }
    ElMessage.success('上传成功')
    showUpload.value = false
    await loadData()
  } catch { ElMessage.error('上传失败') }
  finally { uploading.value = false }
}

function formatSize(bytes: number) {
  if (!bytes) return '-'
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return parseFloat((bytes / Math.pow(1024, i)).toFixed(1)) + ' ' + ['B', 'KB', 'MB', 'GB'][i]
}

function statusLabel(s: string) {
  const map: Record<string, string> = { done: '完成', completed: '完成', processing: '处理中', pending: '等待', failed: '失败' }
  return map[s] || s
}
</script>

<style scoped>
.page { height: 100%; display: flex; flex-direction: column; background: var(--color-bg); }

/* Header */
.page-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-5) var(--space-8);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}
.header-left { display: flex; align-items: center; gap: var(--space-4); }
.back-btn {
  display: flex; align-items: center; gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg); border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); color: var(--color-text-secondary);
  font-size: var(--text-sm); cursor: pointer; font-family: var(--font-sans);
  transition: all var(--transition-fast);
}
.back-btn:hover { background: var(--color-bg-tertiary); color: var(--color-text); }
.header-info h1 { font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--color-text); }
.header-info p { font-size: var(--text-sm); color: var(--color-text-secondary); margin-top: 2px; }
.header-actions { display: flex; gap: var(--space-3); }

.btn-primary {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--color-primary); border: none; border-radius: var(--radius-md);
  color: #fff; font-size: var(--text-sm); font-weight: var(--font-medium);
  cursor: pointer; font-family: var(--font-sans); transition: background var(--transition-fast);
}
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-md);
  color: var(--color-text-secondary); font-size: var(--text-sm);
  cursor: pointer; font-family: var(--font-sans); transition: all var(--transition-fast);
}
.btn-secondary:hover { background: var(--color-bg-tertiary); color: var(--color-text); }

/* Stats Bar */
.stats-bar {
  display: flex; gap: var(--space-8);
  padding: var(--space-4) var(--space-8);
  background: var(--color-surface); border-bottom: 1px solid var(--color-border);
}
.stat { text-align: center; }
.stat-value { display: block; font-size: var(--text-xl); font-weight: var(--font-bold); color: var(--color-primary); }
.stat-label { font-size: var(--text-xs); color: var(--color-text-tertiary); }

/* Tabs */
.tabs {
  display: flex; gap: 0;
  padding: 0 var(--space-8);
  background: var(--color-surface); border-bottom: 1px solid var(--color-border);
}
.tabs button {
  padding: var(--space-3) var(--space-4);
  background: none; border: none; border-bottom: 2px solid transparent;
  color: var(--color-text-secondary); font-size: var(--text-sm); font-weight: var(--font-medium);
  cursor: pointer; font-family: var(--font-sans); transition: all var(--transition-fast);
}
.tabs button:hover { color: var(--color-text); }
.tabs button.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }

/* Content */
.page-content { flex: 1; overflow-y: auto; padding: var(--space-6) var(--space-8); }

.loading-state { display: flex; justify-content: center; padding: var(--space-16); }
.spinner {
  width: 32px; height: 32px; border: 3px solid var(--color-border);
  border-top-color: var(--color-primary); border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: var(--space-16); gap: var(--space-4); color: var(--color-text-secondary);
}

/* Doc List */
.doc-list {
  background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg);
  overflow: hidden;
}
.doc-item {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-3) var(--space-5); border-bottom: 1px solid var(--color-border-light);
  transition: background var(--transition-fast);
}
.doc-item:last-child { border-bottom: none; }
.doc-item:hover { background: var(--color-bg-secondary); }
.doc-icon { flex-shrink: 0; }
.doc-info { flex: 1; }
.doc-name { display: block; font-size: var(--text-sm); font-weight: var(--font-medium); color: var(--color-text); }
.doc-meta { font-size: var(--text-xs); color: var(--color-text-tertiary); }
.doc-status {
  font-size: var(--text-xs); padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full); font-weight: var(--font-medium);
}
.doc-status.done, .doc-status.completed { background: var(--color-primary-light); color: var(--color-primary); }
.doc-status.processing { background: #fef3c7; color: #d97706; }
.doc-status.failed { background: #fee2e2; color: #dc2626; }
.doc-status.pending { background: var(--color-bg-tertiary); color: var(--color-text-tertiary); }

/* Document progress */
.doc-progress {
  margin-top: var(--space-2);
  padding-left: calc(28px + var(--space-3));
}
.progress-bar {
  height: 4px;
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: var(--space-1);
}
.progress-fill {
  height: 100%;
  background: var(--color-primary);
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
}
.progress-text {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}
.doc-action {
  opacity: 0; display: flex; padding: var(--space-1); background: none; border: none;
  border-radius: var(--radius-sm); color: var(--color-text-tertiary); cursor: pointer; transition: all var(--transition-fast);
}
.doc-item:hover .doc-action { opacity: 1; }
.doc-action:hover { background: var(--color-error); color: #fff; }

/* Chunk search & list */
.chunk-search { display: flex; gap: var(--space-3); margin-bottom: var(--space-6); }
.chunk-search input {
  flex: 1; padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: var(--text-sm); color: var(--color-text); outline: none;
  font-family: var(--font-sans); background: var(--color-surface);
  transition: border-color var(--transition-fast);
}
.chunk-search input:focus { border-color: var(--color-primary); box-shadow: 0 0 0 2px var(--color-primary-light); }

.chunk-list { display: flex; flex-direction: column; gap: var(--space-4); }
.chunk-item { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--space-4); }
.chunk-header { display: flex; justify-content: space-between; margin-bottom: var(--space-3); }
.chunk-idx { font-weight: var(--font-semibold); color: var(--color-primary); font-size: var(--text-sm); }
.chunk-source { font-size: var(--text-xs); color: var(--color-text-tertiary); }
.chunk-text { font-size: var(--text-sm); color: var(--color-text); line-height: var(--leading-normal); }

/* Stats */
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: var(--space-4); }
.stat-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg); padding: var(--space-5); }
.stat-card h3 { font-size: var(--text-sm); font-weight: var(--font-semibold); color: var(--color-primary); margin-bottom: var(--space-4); }
.stat-row { display: flex; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-light); }
.stat-row:last-child { border-bottom: none; }
.stat-row span { font-size: var(--text-sm); color: var(--color-text-secondary); }
.stat-row b { font-size: var(--text-sm); color: var(--color-text); }

/* Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 200;
  backdrop-filter: blur(4px);
}
.modal-panel {
  width: 420px; max-height: 80vh;
  background: var(--color-surface); border: 1px solid var(--color-border);
  border-radius: var(--radius-xl); box-shadow: var(--shadow-lg); overflow: hidden;
}
.modal-lg { width: 580px; }
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-4) var(--space-5); border-bottom: 1px solid var(--color-border);
}
.modal-header h2 { font-size: var(--text-lg); font-weight: var(--font-semibold); color: var(--color-text); }
.modal-close {
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  background: none; border: none; border-radius: var(--radius-sm);
  color: var(--color-text-tertiary); cursor: pointer;
}
.modal-close:hover { background: var(--color-bg-tertiary); color: var(--color-text); }
.modal-body { padding: var(--space-5); overflow-y: auto; }

.upload-zone {
  border: 2px dashed var(--color-border); border-radius: var(--radius-lg);
  padding: var(--space-10); text-align: center; cursor: pointer;
  transition: border-color var(--transition-fast);
}
.upload-zone:hover { border-color: var(--color-primary); }
.upload-zone p { margin-top: var(--space-3); font-size: var(--text-sm); color: var(--color-text-secondary); }
.hint { font-size: var(--text-xs) !important; color: var(--color-text-tertiary) !important; }

.upload-progress { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-4); }
.progress-bar { flex: 1; height: 4px; background: var(--color-bg-tertiary); border-radius: var(--radius-full); overflow: hidden; }
.progress-fill { height: 100%; background: var(--color-primary); border-radius: var(--radius-full); transition: width var(--transition-normal); }

.test-input-row { display: flex; gap: var(--space-3); margin-bottom: var(--space-4); }
.test-input-row input {
  flex: 1; padding: var(--space-2) var(--space-4);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: var(--text-sm); color: var(--color-text); outline: none; font-family: var(--font-sans);
}
.test-input-row input:focus { border-color: var(--color-primary); }
.test-options { display: flex; gap: var(--space-6); margin-bottom: var(--space-4); font-size: var(--text-sm); color: var(--color-text-secondary); }
.test-options input[type="number"] { width: 60px; padding: var(--space-1) var(--space-2); border: 1px solid var(--color-border); border-radius: var(--radius-sm); }
.test-options input[type="range"] { width: 80px; accent-color: var(--color-primary); }

.test-results { max-height: 400px; overflow-y: auto; }
.test-results h4 { font-size: var(--text-sm); font-weight: var(--font-semibold); margin-bottom: var(--space-3); }
.result-item { background: var(--color-bg-secondary); padding: var(--space-3); border-radius: var(--radius-md); margin-bottom: var(--space-3); }
.result-header { display: flex; justify-content: space-between; margin-bottom: var(--space-2); }
.result-score { font-weight: var(--font-semibold); color: var(--color-primary); font-size: var(--text-xs); }
.result-file { font-size: var(--text-xs); color: var(--color-text-tertiary); }
.result-content { font-size: var(--text-sm); color: var(--color-text); line-height: var(--leading-normal); }

/* Batch operations */
.batch-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--color-bg-secondary); border-radius: var(--radius-md);
  margin-bottom: var(--space-4);
}
.batch-select-all {
  display: flex; align-items: center; gap: var(--space-2);
  font-size: var(--text-sm); color: var(--color-text-secondary); cursor: pointer;
}
.batch-select-all input { accent-color: var(--color-primary); }
.batch-actions { display: flex; align-items: center; gap: var(--space-3); }
.batch-count { font-size: var(--text-sm); color: var(--color-primary); font-weight: var(--font-medium); }
.btn-danger-sm {
  padding: var(--space-1) var(--space-3);
  background: var(--color-error); color: white; border: none;
  border-radius: var(--radius-sm); font-size: var(--text-xs); cursor: pointer;
}
.btn-danger-sm:hover { opacity: 0.9; }
.doc-checkbox { accent-color: var(--color-primary); cursor: pointer; }

/* Tags */
.doc-tags {
  display: flex; flex-wrap: wrap; gap: var(--space-1); margin-top: var(--space-1);
}
.tag-chip {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 1px 6px; background: var(--color-primary-light); color: var(--color-primary);
  border-radius: var(--radius-full); font-size: 10px; font-weight: var(--font-medium);
}
.tag-remove {
  background: none; border: none; color: var(--color-primary);
  cursor: pointer; font-size: 12px; line-height: 1; padding: 0 2px;
}
.tag-remove:hover { color: var(--color-error); }
.tag-add-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px; border-radius: 50%;
  background: var(--color-bg-tertiary); border: 1px dashed var(--color-border);
  color: var(--color-text-tertiary); font-size: 12px; cursor: pointer;
}
.tag-add-btn:hover { border-color: var(--color-primary); color: var(--color-primary); }

.modal-sm .modal-panel { max-width: 360px; }
.tag-input {
  width: 100%; padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border); border-radius: var(--radius-md);
  font-size: var(--text-sm); color: var(--color-text); outline: none;
  font-family: var(--font-sans);
}
.tag-input:focus { border-color: var(--color-primary); }
.tag-suggestions {
  display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-3);
}
.tag-suggestion {
  padding: var(--space-1) var(--space-3);
  background: var(--color-bg-secondary); border: 1px solid var(--color-border);
  border-radius: var(--radius-full); font-size: var(--text-xs);
  color: var(--color-text-secondary); cursor: pointer;
}
.tag-suggestion:hover { border-color: var(--color-primary); color: var(--color-primary); }
.modal-footer {
  display: flex; justify-content: flex-end; gap: var(--space-3);
  padding: var(--space-4); border-top: 1px solid var(--color-border);
}
</style>
