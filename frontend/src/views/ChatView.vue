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
              <button class="retry-btn" @click="handleRetry" title="重试">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
                重试
              </button>
            </div>

            <!-- Text content (with edit mode) -->
            <div v-if="editingMsgId === msg.id" class="msg-edit">
              <textarea v-model="editText" class="edit-textarea" rows="2" ref="editInput"></textarea>
              <div class="edit-actions">
                <button class="edit-save" @click="saveEdit(msg.id)">保存并重新发送</button>
                <button class="edit-cancel" @click="cancelEdit">取消</button>
              </div>
            </div>
            <div v-else class="msg-text" v-html="formatMarkdown(msg.content)"></div>

            <!-- Edit button for user messages -->
            <div v-if="msg.role === 'user' && msg.type === 'text' && editingMsgId !== msg.id" class="msg-actions">
              <button
                class="action-btn"
                @click="startEdit(msg.id, msg.content)"
                title="编辑消息"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
                <span>编辑</span>
              </button>
            </div>

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

            <!-- Branch button for assistant messages -->
            <div v-if="msg.role === 'assistant' && msg.type === 'text'" class="msg-actions">
              <button
                class="action-btn"
                @click="handleCopyMessage(msg.content)"
                title="复制回答"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
                <span>复制</span>
              </button>
              <button
                class="action-btn"
                @click="handleRegenerate(msg.id)"
                title="重新生成"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
                <span>重新生成</span>
              </button>
              <button
                class="action-btn branch-btn"
                @click="handleBranchClick(msg.id)"
                title="从此处分叉对话"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>
                </svg>
                <span>分叉</span>
              </button>
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
      <div
        class="input-container"
        @dragover.prevent="onDragOver"
        @dragleave="onDragLeave"
        @drop.prevent="onDrop"
        :class="{ 'drag-over': isDragging }"
      >
        <div class="input-tools">
          <button class="tool-btn" @click="showSearchModal = true" title="搜索历史对话">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <span>搜索</span>
          </button>
          <button class="tool-btn" @click="handleExport('markdown')" title="导出对话" :disabled="chatStore.messages.length === 0">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            <span>导出</span>
          </button>
          <button class="tool-btn" @click="showBranchPanel = !showBranchPanel; loadBranches()" title="对话分支">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>
            </svg>
            <span>分支</span>
          </button>
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
          <button class="tool-btn" @click="showTemplatePicker = true" title="提示词模板">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            <span>模板</span>
          </button>
          <button class="tool-btn" @click="handleImageUpload" title="上传图片">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>
            </svg>
          </button>
          <input ref="imageInput" type="file" accept="image/*" hidden @change="onImageSelected" />
          <button class="tool-btn" @click="handleShare" title="分享对话" :disabled="chatStore.messages.length === 0">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
            </svg>
            <span>分享</span>
          </button>
        </div>

        <div class="input-box">
          <textarea
            v-model="inputText"
            ref="inputRef"
            placeholder="输入消息，按 Enter 发送，Shift+Enter 换行..."
            :disabled="chatStore.loading"
            rows="1"
            @keydown="handleKeydown"
            @input="onInput"
          ></textarea>
          <button
            v-if="chatStore.loading"
            class="send-btn stop-btn"
            @click="handleStop"
            title="停止生成 (Escape)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2"/>
            </svg>
          </button>
          <button
            v-else
            class="send-btn"
            @click="handleSend"
            :disabled="!inputText.trim()"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>

        <!-- Suggestions dropdown -->
        <div v-if="showSuggestions" class="suggestions-dropdown">
          <div
            v-for="(s, i) in inputSuggestions"
            :key="i"
            class="suggestion-item"
            @click="applySuggestion(s)"
          >
            {{ s.slice(0, 80) }}{{ s.length > 80 ? '...' : '' }}
          </div>
        </div>

        <div class="input-footer">
          MindPilot 可能会出错，请核实重要信息
        </div>
      </div>
    </div>

    <!-- Knowledge Picker Modal -->
    <KnowledgePicker
      v-if="showKnowledgePicker"
      :knowledge-bases="knowledgeBases"
      :selected-id="selectedKnowledge?.id"
      @close="showKnowledgePicker = false"
      @select="selectKnowledge"
    />

    <!-- Model Picker Modal -->
    <ModelPicker
      v-if="showModelPicker"
      :models="models"
      :current-model="currentModel"
      @close="showModelPicker = false"
      @select="selectModel"
    />

    <!-- Template Picker Modal -->
    <TemplatePicker
      v-if="showTemplatePicker"
      @close="showTemplatePicker = false"
      @select="selectTemplate"
    />

    <!-- Conversation Search Modal -->
    <SearchModal
      v-if="showSearchModal"
      @close="showSearchModal = false"
      @go-to-session="goToSession"
    />

    <!-- Branch Panel -->
    <div v-if="showBranchPanel" class="branch-panel-overlay" @click.self="showBranchPanel = false">
      <BranchTree
        :branches="branches"
        :main-branch="{ message_count: branchMessageCount }"
        :current-branch-id="currentBranchId"
        :can-create-branch="chatStore.messages.length > 0"
        @switch="switchBranch"
        @create="createBranchFromLastMessage"
        @delete="deleteBranch"
        @close="showBranchPanel = false"
      />
    </div>

    <!-- Share Dialog -->
    <el-dialog v-model="showShareDialog" title="分享对话" width="420px" :close-on-click-modal="true">
      <div class="share-dialog-content">
        <p class="share-desc">通过以下链接分享此对话，任何人都可以查看：</p>
        <div class="share-link-row">
          <input :value="shareUrl" readonly class="share-link-input" />
          <button class="share-copy-btn" @click="copyShareUrl">复制</button>
        </div>
      </div>
      <template #footer>
        <button class="share-unshare-btn" @click="handleUnshare">取消分享</button>
        <button class="share-close-btn" @click="showShareDialog = false">关闭</button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { renderMarkdown } from '@/utils/markdown'
import { useChatStore } from '@/stores/chat'
import { chatApi } from '@/api/chat'
import { branchesApi, type Branch } from '@/api/branches'
import type { KnowledgeBase } from '@/api/types'
import BranchTree from '@/components/BranchTree.vue'
import KnowledgePicker from '@/components/KnowledgePicker.vue'
import ModelPicker from '@/components/ModelPicker.vue'
import SearchModal from '@/components/SearchModal.vue'
import TemplatePicker from '@/components/TemplatePicker.vue'
import api from '@/api/index'

const route = useRoute()
const chatStore = useChatStore()

const inputText = ref('')
const chatContainer = ref<HTMLElement>()
const inputRef = ref<HTMLTextAreaElement>()
const imageInput = ref<HTMLInputElement>()

const showKnowledgePicker = ref(false)
const showModelPicker = ref(false)
const showSearchModal = ref(false)
const showBranchPanel = ref(false)
const showTemplatePicker = ref(false)
const isDragging = ref(false)
const knowledgeBases = ref<KnowledgeBase[]>([])
const selectedKnowledge = ref<KnowledgeBase | null>(null)
const currentModel = ref('glm-4-flash')
const expandedSources = ref(new Set<string>())
const selectedImageBase64 = ref<string | null>(null)
const selectedImageName = ref<string>('')
const editingMsgId = ref<string | null>(null)
const editText = ref('')
const editInput = ref<HTMLTextAreaElement>()
const inputSuggestions = ref<string[]>([])
const showSuggestions = ref(false)

// Branch state
const branches = ref<Branch[]>([])
const currentBranchId = ref<string | null>(null)
const selectedMessageId = ref<string | null>(null)
const branchMessageCount = ref(0)

const MODEL_DESCRIPTIONS: Record<string, string> = {
  'glm-4-flash': '快速响应，适合日常对话',
  'glm-4-plus': '增强版，更高质量回答',
  'glm-4-long': '超长上下文，适合长文档',
  'glm-4-air': '轻量版，性价比高',
  'glm-4-airx': '轻量增强版，速度与质量平衡',
  'glm-4v-plus': '多模态，支持图像理解',
}

const models = ref<{ id: string; label: string; desc: string }[]>([])

async function loadModels() {
  try {
    const res = await api.get('/health/models')
    const data = res.data
    models.value = (data.models || []).map((id: string) => ({
      id,
      label: id.toUpperCase().replace(/-/g, ' '),
      desc: MODEL_DESCRIPTIONS[id] || '语言模型',
    }))
    // Set default from server
    if (data.default && !currentModel.value) {
      currentModel.value = data.default
    }
  } catch {
    // Fallback to hardcoded models
    models.value = [
      { id: 'glm-4-flash', label: 'GLM-4-FLASH', desc: '快速响应，适合日常对话' },
    ]
  }
}

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
  await Promise.all([loadKnowledgeBases(), loadModels()])

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
  } catch (err) {
    console.warn('Failed to load knowledge bases:', err)
  }
}

function handleSuggestion(q: string) {
  inputText.value = q
  handleSend()
}

async function handleExport(format: 'markdown' | 'json' = 'markdown') {
  if (chatStore.messages.length === 0) return
  try {
    await chatApi.exportSession(chatStore.currentSessionId, format)
    ElMessage.success('导出成功')
  } catch (err) {
    console.error('Export failed:', err)
    ElMessage.error('导出失败')
  }
}

const shareUrl = ref('')
const showShareDialog = ref(false)

async function handleShare() {
  if (chatStore.messages.length === 0) return
  if (!chatStore.currentSessionId) return
  try {
    const result = await chatApi.shareSession(chatStore.currentSessionId)
    shareUrl.value = `${window.location.origin}/share/${result.share_id}`
    showShareDialog.value = true
    ElMessage.success('分享链接已生成')
  } catch (err) {
    console.error('Share failed:', err)
    ElMessage.error('生成分享链接失败')
  }
}

function copyShareUrl() {
  navigator.clipboard.writeText(shareUrl.value)
  ElMessage.success('链接已复制')
}

async function handleUnshare() {
  if (!chatStore.currentSessionId) return
  try {
    await chatApi.unshareSession(chatStore.currentSessionId)
    showShareDialog.value = false
    shareUrl.value = ''
    ElMessage.success('已取消分享')
  } catch (err) {
    ElMessage.error('取消分享失败')
  }
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

function selectKnowledge(kb: KnowledgeBase) {
  selectedKnowledge.value = kb
  showKnowledgePicker.value = false
}

function selectModel(id: string) {
  currentModel.value = id
  showModelPicker.value = false
}

function selectTemplate(content: string) {
  inputText.value = content
  showTemplatePicker.value = false
  nextTick(() => {
    inputRef.value?.focus()
    autoResize()
  })
}

function handleStop() {
  chatStore.abortStream()
  chatStore.loading = false
  chatStore.streamingStatus = ''
}

function handleRetry() {
  // Find the last user message and resend it
  const lastUserMsg = [...chatStore.messages].reverse().find(m => m.role === 'user')
  if (lastUserMsg) {
    // Remove error messages after the last user message
    const userIdx = chatStore.messages.findIndex(m => m.id === lastUserMsg.id)
    const toRemove = chatStore.messages.slice(userIdx + 1).filter(m => m.type === 'error')
    toRemove.forEach(m => chatStore.removeMessage(m.id))

    chatStore.sendMessage(lastUserMsg.content, {
      knowledgeId: selectedKnowledge.value?.id,
      model: currentModel.value,
    })
  }
}

function handleRegenerate(assistantMsgId: string) {
  // Find the user message before this assistant message
  const msgIdx = chatStore.messages.findIndex(m => m.id === assistantMsgId)
  if (msgIdx < 0) return

  // Look backwards for the user message
  let userMsg: Message | null = null
  for (let i = msgIdx - 1; i >= 0; i--) {
    if (chatStore.messages[i].role === 'user') {
      userMsg = chatStore.messages[i]
      break
    }
  }
  if (!userMsg) return

  // Remove the assistant message and any status messages after it
  chatStore.removeMessage(assistantMsgId)
  const toRemove = chatStore.messages.slice(msgIdx).filter(m => m.type === 'status' || m.type === 'error')
  toRemove.forEach(m => chatStore.removeMessage(m.id))

  chatStore.sendMessage(userMsg.content, {
    knowledgeId: selectedKnowledge.value?.id,
    model: currentModel.value,
  })
}

async function handleCopyMessage(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

function handleKeydown(e: KeyboardEvent) {
  // Escape: close modals or stop generating
  if (e.key === 'Escape') {
    if (chatStore.loading) {
      handleStop()
      return
    }
    showKnowledgePicker.value = false
    showModelPicker.value = false
    showTemplatePicker.value = false
    showSearchModal.value = false
    showBranchPanel.value = false
    showShareDialog.value = false
    return
  }
  // Ctrl+K: open search
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault()
    showSearchModal.value = true
    return
  }
  // Enter to send (exact match, no modifiers)
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
    e.preventDefault()
    handleSend()
  }
}

function autoResize() {
  nextTick(() => {
    const el = inputRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  })
}

// ── Edit message ──

function startEdit(msgId: string, content: string) {
  editingMsgId.value = msgId
  editText.value = content
  nextTick(() => editInput.value?.focus())
}

function cancelEdit() {
  editingMsgId.value = null
  editText.value = ''
}

async function saveEdit(msgId: string) {
  if (!editText.value.trim()) return
  try {
    await api.put(`/chat/messages/${msgId}`, { content: editText.value.trim() })
    // Reload the session to get updated messages
    if (chatStore.currentSessionId) {
      await chatStore.loadSession(chatStore.currentSessionId)
    }
    editingMsgId.value = null
    editText.value = ''
    // Re-send with the edited content
    await chatStore.sendMessage(editText.value.trim() || '', {
      knowledgeId: selectedKnowledge.value?.id,
      model: currentModel.value,
    })
  } catch (err) {
    console.error('Failed to edit message:', err)
    ElMessage.error('编辑失败')
  }
}

// ── Input suggestions ──

function updateSuggestions() {
  const text = inputText.value.trim()
  if (text.length < 2) {
    showSuggestions.value = false
    return
  }
  // Match against recent user messages
  const recent = chatStore.messages
    .filter(m => m.role === 'user' && m.content.includes(text) && m.content !== text)
    .map(m => m.content)
    .slice(0, 3)
  // Match against templates
  const tplMatches: string[] = []
  inputSuggestions.value = [...new Set([...recent, ...tplMatches])].slice(0, 5)
  showSuggestions.value = inputSuggestions.value.length > 0
}

function applySuggestion(text: string) {
  inputText.value = text
  showSuggestions.value = false
  nextTick(() => inputRef.value?.focus())
}

function onInput() {
  autoResize()
  updateSuggestions()
}

// ── Drag and drop ──

function onDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave() {
  isDragging.value = false
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const files = e.dataTransfer?.files
  if (!files?.length) return

  const file = files[0]
  if (file.type.startsWith('image/')) {
    if (file.size > 10 * 1024 * 1024) {
      ElMessage.warning('图片大小不能超过 10MB')
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
  } else if (file.name.match(/\.(pdf|docx?|pptx?|txt|md)$/i)) {
    // Redirect to knowledge upload
    ElMessage.info('请在知识库页面上传文档')
  }
}

function goToSession(sessionId: string) {
  showSearchModal.value = false
  chatStore.loadSession(sessionId)
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
  return renderMarkdown(text)
}

// ── Branch functions ──

async function loadBranches() {
  if (!chatStore.currentSessionId) return
  try {
    const response = await branchesApi.list(chatStore.currentSessionId)
    branches.value = response.branches || []
    branchMessageCount.value = response.main_branch?.message_count || 0
  } catch {
    branches.value = []
  }
}

async function createBranch(messageId: string) {
  if (!chatStore.currentSessionId) return
  selectedMessageId.value = messageId
  try {
    const branch = await branchesApi.create(
      chatStore.currentSessionId,
      messageId,
      `分支 ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
    )
    branches.value.unshift(branch)
    await switchBranch(branch.id)
  } catch (error) {
    console.error('Failed to create branch:', error)
  }
}

async function switchBranch(branchId: string | null) {
  if (!chatStore.currentSessionId) return

  currentBranchId.value = branchId
  showBranchPanel.value = false

  if (branchId) {
    try {
      const response = await branchesApi.get(branchId)
      // Load branch messages into chat store
      chatStore.clearMessages()
      for (const m of response.messages) {
        chatStore.addMessage(
          m.role,
          m.content,
          'text',
          m.metadata?.sources || [],
        )
      }
    } catch (error) {
      console.error('Failed to switch branch:', error)
    }
  } else {
    // Switch back to main branch
    await chatStore.loadSession(chatStore.currentSessionId)
  }
}

async function deleteBranch(branchId: string) {
  try {
    await branchesApi.delete(branchId)
    branches.value = branches.value.filter(b => b.id !== branchId)
    if (currentBranchId.value === branchId) {
      await switchBranch(null)
    }
  } catch (error) {
    console.error('Failed to delete branch:', error)
  }
}

function createBranchFromLastMessage() {
  const lastAssistantMsg = [...chatStore.messages]
    .reverse()
    .find(m => m.role === 'assistant' && m.type === 'text')

  if (lastAssistantMsg) {
    createBranch(lastAssistantMsg.id)
  }
}

function handleBranchClick(messageId: string) {
  createBranch(messageId)
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
  background: var(--color-error-bg);
  border: 1px solid var(--color-error-border);
  border-radius: var(--radius-sm);
  color: var(--color-error);
  font-size: var(--text-sm);
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

/* Code block with copy button */
.msg-text :deep(.code-block) {
  position: relative;
  margin: var(--space-3) 0;
}
.msg-text :deep(.code-block pre) {
  margin: 0;
}
.msg-text :deep(.code-copy-btn) {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-sm);
  color: #94a3b8;
  font-size: var(--text-xs);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--transition-fast);
  font-family: var(--font-sans);
}
.msg-text :deep(.code-block:hover .code-copy-btn) {
  opacity: 1;
}
.msg-text :deep(.code-copy-btn:hover) {
  background: rgba(255, 255, 255, 0.2);
  color: #e2e8f0;
}
.msg-text :deep(.code-lang) {
  position: absolute;
  top: var(--space-2);
  left: var(--space-3);
  color: #64748b;
  font-size: var(--text-xs);
  font-family: var(--font-mono);
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

/* Message actions */
.msg-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
  opacity: 0;
  transition: opacity var(--transition-fast);
}
.message-row:hover .msg-actions {
  opacity: 1;
}
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
}
.action-btn:hover {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.branch-btn:hover {
  background: var(--bg-branch);
  border-color: var(--border-branch);
  color: var(--color-branch);
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
  position: relative;
  transition: all var(--transition-fast);
}
.input-container.drag-over {
  border: 2px dashed var(--color-primary);
  border-radius: var(--radius-lg);
  background: var(--color-primary-light);
  padding: var(--space-2);
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
.stop-btn {
  background: var(--color-error);
}
.stop-btn:hover {
  background: #dc2626;
}

/* Retry button in error messages */
.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-2);
  padding: var(--space-1) var(--space-3);
  background: none;
  border: 1px solid var(--color-error-border);
  border-radius: var(--radius-sm);
  color: var(--color-error);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: var(--font-sans);
}
.retry-btn:hover {
  background: var(--color-error-bg);
}

/* Edit mode */
.msg-edit {
  margin-top: var(--space-2);
}
.edit-textarea {
  width: 100%;
  padding: var(--space-2);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  font-family: var(--font-sans);
  line-height: var(--leading-normal);
  color: var(--color-text);
  background: var(--color-bg);
  resize: vertical;
  min-height: 60px;
}
.edit-textarea:focus {
  outline: none;
  box-shadow: 0 0 0 3px var(--color-primary-light);
}
.edit-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
.edit-save {
  padding: var(--space-1) var(--space-3);
  background: var(--color-primary);
  border: none;
  border-radius: var(--radius-sm);
  color: #fff;
  font-size: var(--text-xs);
  cursor: pointer;
  font-family: var(--font-sans);
}
.edit-save:hover { background: var(--color-primary-hover); }
.edit-cancel {
  padding: var(--space-1) var(--space-3);
  background: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
  cursor: pointer;
  font-family: var(--font-sans);
}
.edit-cancel:hover { background: var(--color-bg-tertiary); }

/* Suggestions dropdown */
.suggestions-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  max-height: 200px;
  overflow-y: auto;
  z-index: 10;
  margin-bottom: var(--space-1);
}
.suggestion-item {
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
  border-bottom: 1px solid var(--color-border-light);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.suggestion-item:last-child { border-bottom: none; }
.suggestion-item:hover {
  background: var(--color-bg-secondary);
  color: var(--color-text);
}

.input-footer {
  text-align: center;
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

/* ── Branch Panel ── */
.branch-panel-overlay {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  background: rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  padding: 80px 20px 20px;
  z-index: 100;
}

.branch-panel-overlay :deep(.branch-tree) {
  max-height: calc(100vh - 120px);
}

/* ── Share Dialog ── */
.share-dialog-content {
  padding: var(--space-2) 0;
}
.share-desc {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}
.share-link-row {
  display: flex;
  gap: var(--space-2);
}
.share-link-input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--color-text);
  background: var(--color-bg-secondary);
  font-family: var(--font-mono);
}
.share-copy-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--text-sm);
  white-space: nowrap;
}
.share-copy-btn:hover {
  opacity: 0.9;
}
.share-unshare-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--color-error);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--text-sm);
  margin-right: auto;
}
.share-close-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg-secondary);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--text-sm);
}
</style>
