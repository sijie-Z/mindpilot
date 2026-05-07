<template>
  <div class="chat-page">
    <!-- Messages Area -->
    <div class="chat-container" ref="chatContainer">
      <!-- Welcome state -->
      <div v-if="chatStore.messages.length === 0" class="welcome">
        <div class="welcome-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="1.5">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/>
            <path d="M2 17l10 5 10-5"/>
            <path d="M2 12l10 5 10-5"/>
          </svg>
        </div>
        <h1>欢迎使用 MindPilot</h1>
        <p class="welcome-desc">基于 RAG 技术的智能知识检索助手</p>

        <div class="feature-grid">
          <div class="feature-card">
            <div class="feature-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
              </svg>
            </div>
            <h3>知识问答</h3>
            <p>基于您的知识库提供精准回答</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
            <h3>智能检索</h3>
            <p>向量语义 + 关键词混合检索</p>
          </div>
          <div class="feature-card">
            <div class="feature-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
              </svg>
            </div>
            <h3>来源追溯</h3>
            <p>每个回答附带文档引用来源</p>
          </div>
        </div>

        <div class="suggestions">
          <p>试试这些问题：</p>
          <div class="suggestion-chips">
            <button
              v-for="q in suggestions"
              :key="q"
              class="suggestion-chip"
              @click="handleSuggestion(q)"
            >{{ q }}</button>
          </div>
        </div>
      </div>

      <!-- Message list -->
      <div class="message-list">
        <div
          v-for="msg in visibleMessages"
          :key="msg.id"
          class="message-row"
          :class="msg.role"
        >
          <!-- Avatar -->
          <div class="msg-avatar" :class="msg.role">
            <svg v-if="msg.role === 'assistant'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
            </svg>
            <svg v-else-if="msg.role === 'user'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
          </div>

          <!-- Content -->
          <div class="msg-body">
            <div class="msg-header">
              <span class="msg-role">{{ roleLabel(msg) }}</span>
              <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
            </div>

            <!-- Status message -->
            <div v-if="msg.type === 'status'" class="msg-status">
              <span class="status-dot"></span>
              <span v-if="msg.statusLabel" class="status-label">{{ msg.statusLabel }}</span>
              <span class="status-text">{{ msg.content }}</span>
            </div>

            <!-- Error message -->
            <div v-else-if="msg.type === 'error'" class="msg-error">
              {{ msg.content }}
            </div>

            <!-- Text content -->
            <div v-else class="msg-text" v-html="formatMarkdown(msg.content)"></div>

            <!-- Sources -->
            <div v-if="msg.sources && msg.sources.length > 0" class="msg-sources">
              <div class="sources-header" @click="toggleSources(msg.id)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                </svg>
                参考来源 ({{ msg.sources.length }})
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                  :style="{ transform: expandedSources.has(msg.id) ? 'rotate(180deg)' : '' }">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </div>
              <div v-if="expandedSources.has(msg.id)" class="sources-list">
                <div v-for="(src, i) in msg.sources" :key="i" class="source-item">
                  <span class="source-idx">[{{ i + 1 }}]</span>
                  <span class="source-name">{{ src.filename || src.name || '来源文档' }}</span>
                  <span v-if="src.score !== undefined" class="source-score">{{ (src.score * 100).toFixed(0) }}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading indicator -->
      <div v-if="chatStore.loading && chatStore.messages.length > 0" class="loading-bar">
        <div class="loading-progress"></div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="input-area">
      <div class="input-container">
        <div class="input-tools">
          <button class="tool-btn" @click="showKnowledgePicker = true" title="选择知识库">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            </svg>
            <span>{{ selectedKnowledge?.name || '选择知识库' }}</span>
          </button>
          <button class="tool-btn" @click="showModelPicker = true" title="选择模型">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 6v10M1 12h6m6 0h10"/>
            </svg>
            <span>{{ currentModel }}</span>
          </button>
          <button class="tool-btn" @click="handleImageUpload" title="上传图片">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
            </svg>
          </button>
          <input ref="imageInput" type="file" accept="image/*" hidden @change="onImageSelected" />
        </div>

        <div class="input-box">
          <textarea
            v-model="inputText"
            ref="inputRef"
            placeholder="输入消息，按 Enter 发送，Shift+Enter 换行..."
            :disabled="chatStore.loading"
            rows="1"
            @keydown.enter.exact.prevent="handleSend"
          ></textarea>
          <button
            class="send-btn"
            @click="handleSend"
            :disabled="!inputText.trim() || chatStore.loading"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>

        <div class="input-footer">
          MindPilot 可能会出错，请核实重要信息
        </div>
      </div>
    </div>

    <!-- Knowledge Picker Modal -->
    <div v-if="showKnowledgePicker" class="modal" @click.self="showKnowledgePicker = false">
      <div class="modal-panel">
        <div class="modal-header">
          <h3>选择知识库</h3>
          <button class="modal-close" @click="showKnowledgePicker = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="knowledgeBases.length === 0" class="modal-empty">
            <p>暂无知识库</p>
            <router-link to="/knowledge" class="btn-primary" @click="showKnowledgePicker = false">创建知识库</router-link>
          </div>
          <div v-else class="kb-list">
            <div
              v-for="kb in knowledgeBases"
              :key="kb.id"
              class="kb-item"
              :class="{ selected: selectedKnowledge?.id === kb.id }"
              @click="selectKnowledge(kb)"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
              </svg>
              <div class="kb-info">
                <div class="kb-name">{{ kb.name }}</div>
                <div class="kb-meta">{{ kb.doc_count || 0 }} 文档 · {{ kb.chunk_count || 0 }} 片段</div>
              </div>
              <svg v-if="selectedKnowledge?.id === kb.id" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-primary)" stroke-width="3">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Model Picker Modal -->
    <div v-if="showModelPicker" class="modal" @click.self="showModelPicker = false">
      <div class="modal-panel modal-sm">
        <div class="modal-header">
          <h3>选择模型</h3>
          <button class="modal-close" @click="showModelPicker = false">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div
            v-for="m in models"
            :key="m.id"
            class="model-option"
            :class="{ selected: currentModel === m.id }"
            @click="selectModel(m.id)"
          >
            <div class="model-name">{{ m.label }}</div>
            <div class="model-desc">{{ m.desc }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import { useChatStore } from '@/stores/chat'
import api from '@/api/index'

const route = useRoute()
const chatStore = useChatStore()

const inputText = ref('')
const chatContainer = ref<HTMLElement>()
const inputRef = ref<HTMLTextAreaElement>()
const imageInput = ref<HTMLInputElement>()

const showKnowledgePicker = ref(false)
const showModelPicker = ref(false)
const knowledgeBases = ref<any[]>([])
const selectedKnowledge = ref<any>(null)
const currentModel = ref('glm-4-flash')
const expandedSources = ref(new Set<string>())
const selectedImageBase64 = ref<string | null>(null)
const selectedImageName = ref<string>('')

const models = [
  { id: 'glm-4-flash', label: 'GLM-4-Flash', desc: '快速响应，适合日常对话' },
  { id: 'glm-4', label: 'GLM-4', desc: '标准模型，平衡速度与质量' },
  { id: 'glm-4v-plus', label: 'GLM-4V-Plus', desc: '多模态，支持图像理解' },
]

const suggestions = [
  '什么是 RAG 技术？',
  '如何创建知识库？',
  'MindPilot 有哪些功能？',
  '向量检索和关键词检索有什么区别？',
]

const visibleMessages = computed(() =>
  chatStore.messages.filter(m => m.role !== 'system' || m.type !== 'status')
)

onMounted(async () => {
  await loadKnowledgeBases()

  const sessionId = route.query.session as string
  if (sessionId) {
    await chatStore.loadSession(sessionId)
  }
})

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
})

async function loadKnowledgeBases() {
  try {
    const res = await api.get('/knowledge/')
    knowledgeBases.value = Array.isArray(res.data) ? res.data : (res.data?.knowledges || res.data?.items || [])
    if (knowledgeBases.value.length > 0 && !selectedKnowledge.value) {
      selectedKnowledge.value = knowledgeBases.value[0]
    }
  } catch { /* knowledge API may not be available */ }
}

function handleSuggestion(q: string) {
  inputText.value = q
  handleSend()
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || chatStore.loading) return
  inputText.value = ''

  await chatStore.sendMessage(text, {
    knowledgeId: selectedKnowledge.value?.id,
    model: currentModel.value,
    imageBase64: selectedImageBase64.value || undefined,
  })

  selectedImageBase64.value = null
  selectedImageName.value = ''
  scrollToBottom()
}

function handleImageUpload() {
  imageInput.value?.click()
}

function onImageSelected(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files?.length) return
  const file = files[0]

  if (file.size > 10 * 1024 * 1024) {
    alert('图片大小不能超过 10MB')
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    const result = reader.result as string
    selectedImageBase64.value = result.split(',')[1]
    selectedImageName.value = file.name
    inputText.value = `[图片: ${file.name}] ${inputText.value}`
  }
  reader.readAsDataURL(file)
}

function selectKnowledge(kb: any) {
  selectedKnowledge.value = kb
  showKnowledgePicker.value = false
}

function selectModel(id: string) {
  currentModel.value = id
  showModelPicker.value = false
}

function toggleSources(msgId: string) {
  if (expandedSources.value.has(msgId)) {
    expandedSources.value.delete(msgId)
  } else {
    expandedSources.value.add(msgId)
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function roleLabel(msg: { role: string; type: string }) {
  if (msg.role === 'user') return '你'
  if (msg.role === 'system') return '系统'
  if (msg.type === 'status') return '状态'
  return 'MindPilot'
}

function formatTime(ts: number) {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatMarkdown(text: string) {
  if (!text) return ''
  return marked.parse(text) as string
}
</script>

<style scoped>
.chat-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg);
}

/* ── Chat Container ── */
.chat-container {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
}

/* ── Welcome ── */
.welcome {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-16) var(--space-6);
  text-align: center;
}
.welcome-icon { margin-bottom: var(--space-6); }
.welcome h1 {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--color-text);
  margin-bottom: var(--space-2);
}
.welcome-desc {
  color: var(--color-text-secondary);
  margin-bottom: var(--space-10);
  font-size: var(--text-lg);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-10);
}
.feature-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  text-align: left;
  transition: all var(--transition-fast);
}
.feature-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-sm);
}
.feature-icon {
  width: 40px;
  height: 40px;
  background: var(--color-primary-light);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  margin-bottom: var(--space-4);
}
.feature-card h3 {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--color-text);
  margin-bottom: var(--space-1);
}
.feature-card p {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  line-height: var(--leading-normal);
}

.suggestions p {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}
.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: center;
}
.suggestion-chip {
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: var(--font-sans);
}
.suggestion-chip:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-light);
}

/* ── Messages ── */
.message-list {
  padding: var(--space-4) 0;
}
.message-row {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  max-width: 820px;
  margin: 0 auto;
  transition: background var(--transition-fast);
}
.message-row.user {
  background: var(--color-bg-secondary);
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #fff;
}
.msg-avatar.assistant {
  background: var(--color-primary);
}
.msg-avatar.user {
  background: var(--color-text-tertiary);
}
.msg-avatar.system {
  background: var(--color-warning);
}

.msg-body {
  flex: 1;
  min-width: 0;
}
.msg-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}
.msg-role {
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
  color: var(--color-text);
}
.msg-time {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

/* Status message */
.msg-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-primary-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--color-primary);
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: pulse 1.5s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.status-label {
  font-weight: var(--font-medium);
  font-size: var(--text-xs);
}
.status-text {
  color: var(--color-text-secondary);
}

/* Error message */
.msg-error {
  padding: var(--space-3);
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
  color: var(--color-error);
  font-size: var(--text-sm);
}
.dark .msg-error {
  background: #451a1a;
  border-color: #7f1d1d;
}

/* Text message */
.msg-text {
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  color: var(--color-text);
}
.msg-text :deep(p) { margin-bottom: var(--space-3); }
.msg-text :deep(p:last-child) { margin-bottom: 0; }
.msg-text :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.875em;
  background: var(--color-bg-tertiary);
  padding: 0.15em 0.4em;
  border-radius: var(--radius-sm);
}
.msg-text :deep(pre) {
  background: #1e293b;
  color: #e2e8f0;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin: var(--space-3) 0;
  font-size: var(--text-sm);
}
.msg-text :deep(pre code) {
  background: none;
  padding: 0;
}
.msg-text :deep(ul), .msg-text :deep(ol) {
  padding-left: var(--space-6);
  margin: var(--space-3) 0;
}
.msg-text :deep(li) { margin-bottom: var(--space-1); }
.msg-text :deep(blockquote) {
  border-left: 3px solid var(--color-primary);
  padding-left: var(--space-4);
  color: var(--color-text-secondary);
  margin: var(--space-3) 0;
}

/* Sources */
.msg-sources {
  margin-top: var(--space-4);
  padding: var(--space-3);
  background: var(--color-bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
}
.sources-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--color-primary);
  cursor: pointer;
  user-select: none;
}
.sources-list {
  margin-top: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.source-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
}
.source-idx {
  color: var(--color-primary);
  font-weight: var(--font-semibold);
}
.source-name {
  flex: 1;
  color: var(--color-text);
}
.source-score {
  color: var(--color-text-tertiary);
  font-weight: var(--font-medium);
}

/* Loading bar */
.loading-bar {
  max-width: 820px;
  margin: 0 auto;
  padding: 0 var(--space-6);
}
.loading-progress {
  height: 2px;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-light), var(--color-primary));
  background-size: 200% 100%;
  animation: loadingSlide 1.5s infinite;
  border-radius: var(--radius-full);
}
@keyframes loadingSlide {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Input Area ── */
.input-area {
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
  padding: var(--space-4) var(--space-6) var(--space-6);
}
.input-container {
  max-width: 820px;
  margin: 0 auto;
}
.input-tools {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.tool-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: var(--font-sans);
}
.tool-btn:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-primary);
  color: var(--color-text);
}
.tool-btn svg { color: var(--color-text-tertiary); flex-shrink: 0; }

.input-box {
  display: flex;
  gap: var(--space-3);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: var(--space-2) var(--space-3);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}
.input-box:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}
.input-box textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: var(--text-base);
  font-family: var(--font-sans);
  line-height: var(--leading-normal);
  color: var(--color-text);
  background: transparent;
  min-height: 24px;
  max-height: 200px;
  padding: var(--space-1) 0;
}
.input-box textarea::placeholder {
  color: var(--color-text-tertiary);
}
.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  cursor: pointer;
  flex-shrink: 0;
  align-self: flex-end;
  transition: background var(--transition-fast);
}
.send-btn:hover { background: var(--color-primary-hover); }
.send-btn:disabled {
  background: var(--color-border);
  cursor: not-allowed;
}

.input-footer {
  text-align: center;
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

/* ── Modals ── */
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
.modal-sm { width: 360px; }
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
.modal-empty {
  text-align: center;
  padding: var(--space-8);
  color: var(--color-text-secondary);
}
.modal-empty p { margin-bottom: var(--space-4); }

.btn-primary {
  display: inline-block;
  padding: var(--space-2) var(--space-5);
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  text-decoration: none;
  font-family: var(--font-sans);
}
.btn-primary:hover { background: var(--color-primary-hover); }

.kb-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.kb-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--color-bg-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.kb-item:hover { background: var(--color-bg-tertiary); }
.kb-item.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.kb-item svg { color: var(--color-text-tertiary); flex-shrink: 0; }
.kb-item.selected svg { color: var(--color-primary); }
.kb-info { flex: 1; }
.kb-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
}
.kb-meta {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

.model-option {
  padding: var(--space-3);
  background: var(--color-bg-secondary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  margin-bottom: var(--space-2);
  transition: all var(--transition-fast);
}
.model-option:last-child { margin-bottom: 0; }
.model-option:hover { background: var(--color-bg-tertiary); }
.model-option.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}
.model-name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--color-text);
}
.model-desc {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}
</style>
