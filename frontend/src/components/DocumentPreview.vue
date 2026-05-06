<template>
  <el-dialog
    v-model="visible"
    :title="document?.name || '文档预览'"
    width="800px"
    destroy-on-close
    class="document-preview"
  >
    <div v-if="loading" class="preview-loading">
      <el-skeleton :rows="10" animated />
    </div>

    <div v-else-if="error" class="preview-error">
      <el-empty description="加载失败">
        <el-button type="primary" @click="loadContent">重试</el-button>
      </el-empty>
    </div>

    <div v-else class="preview-content">
      <div class="doc-meta">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="文件名">{{ document?.name }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ document?.category || '未分类' }}</el-descriptions-item>
          <el-descriptions-item label="大小">{{ formatSize(document?.size_bytes) }}</el-descriptions-item>
          <el-descriptions-item label="片段数">{{ document?.chunk_count || 0 }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType(document?.status)" size="small">
              {{ statusText(document?.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="上传时间">{{ formatDate(document?.created_at) }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <el-divider />

      <el-tabs v-model="activeTab">
        <el-tab-pane label="内容预览" name="content">
          <div class="content-panel">
            <div v-if="content" class="content-text" v-html="renderContent(content)"></div>
            <el-empty v-else description="暂无内容" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="片段列表" name="chunks">
          <div class="chunks-panel">
            <div v-if="chunks.length > 0">
              <div v-for="(chunk, index) in chunks" :key="index" class="chunk-card">
                <div class="chunk-card-header">
                  <span class="chunk-idx">#{{ index + 1 }}</span>
                  <span class="chunk-chars">约 {{ chunk.content?.length || 0 }} 字符</span>
                </div>
                <div class="chunk-card-body">{{ truncate(chunk.content, 200) }}</div>
              </div>
            </div>
            <el-empty v-else description="暂无片段" />
          </div>
        </el-tab-pane>

        <el-tab-pane label="元数据" name="metadata">
          <div class="metadata-panel">
            <pre v-if="metadata">{{ JSON.stringify(metadata, null, 2) }}</pre>
            <el-empty v-else description="暂无元数据" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" @click="downloadDocument">下载原文</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api/index'

interface Props {
  modelValue: boolean
  document: any
}

const props = defineProps<Props>()
const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const loading = ref(false)
const error = ref(false)
const activeTab = ref('content')
const content = ref('')
const chunks = ref<any[]>([])
const metadata = ref<any>(null)

watch(visible, (val) => {
  if (val && props.document) loadContent()
})

async function loadContent() {
  if (!props.document?.id) return
  loading.value = true
  error.value = false

  try {
    const res = await api.get(`/document/${props.document.id}`)
    content.value = res.data.content || ''
    chunks.value = res.data.chunks || []
    metadata.value = res.data.metadata || null
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function formatSize(bytes?: number): string {
  if (!bytes) return '未知'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatDate(date?: string): string {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}

function statusType(status?: string): string {
  const t: Record<string, string> = { completed: 'success', processing: 'warning', pending: 'info', failed: 'danger' }
  return t[status || 'pending'] || 'info'
}

function statusText(status?: string): string {
  const t: Record<string, string> = { completed: '已完成', processing: '处理中', pending: '等待中', failed: '失败' }
  return t[status || 'pending'] || status || '未知'
}

function renderContent(text: string): string {
  if (!text) return ''
  return text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
}

function truncate(text: string, max: number): string {
  if (!text || text.length <= max) return text || ''
  return text.substring(0, max) + '...'
}

async function downloadDocument() {
  if (!props.document?.id) return
  try {
    const res = await api.get(`/document/${props.document.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = props.document.name || 'document'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch {
    ElMessage.error('下载失败')
  }
}
</script>

<style scoped>
.preview-loading, .preview-error { padding: var(--space-8); }

.doc-meta { margin-bottom: var(--space-5); }

.content-panel {
  max-height: 400px; overflow-y: auto; padding: var(--space-4);
  background: var(--color-bg-secondary); border-radius: var(--radius-md);
}
.content-text {
  line-height: var(--leading-relaxed);
  white-space: pre-wrap; word-break: break-word;
  font-size: var(--text-sm); color: var(--color-text);
}

.chunks-panel { max-height: 400px; overflow-y: auto; }
.chunk-card {
  padding: var(--space-3); margin-bottom: var(--space-3);
  background: var(--color-bg-secondary); border-radius: var(--radius-md);
  border-left: 3px solid var(--color-primary);
}
.chunk-card-header {
  display: flex; justify-content: space-between; margin-bottom: var(--space-2);
  font-size: var(--text-xs); color: var(--color-text-secondary);
}
.chunk-idx { font-weight: var(--font-semibold); color: var(--color-primary); }
.chunk-card-body {
  font-size: var(--text-sm); color: var(--color-text);
  line-height: var(--leading-normal);
}

.metadata-panel { max-height: 400px; overflow-y: auto; }
.metadata-panel pre {
  background: var(--color-bg-secondary); padding: var(--space-4);
  border-radius: var(--radius-md); font-size: var(--text-xs); overflow-x: auto;
  color: var(--color-text);
}
</style>
