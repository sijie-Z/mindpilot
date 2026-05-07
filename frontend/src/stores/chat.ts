/**
 * Chat store for MindPilot.
 * Uses backend session API for persistence, localStorage as fallback cache.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi, type SSEData } from '@/api/chat'
import api from '@/api/index'

export interface Source {
  filename?: string
  name?: string
  chunk_id?: string
  content?: string
  score?: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  type: 'text' | 'status' | 'error'
  content: string
  sources?: Source[]
  statusLabel?: string
  timestamp: number
}

export interface ChatSession {
  id: string
  title: string
  messages: Message[]
  created_at: string
  updated_at: string
}

const STORAGE_KEY = 'mindpilot_chat_sessions'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const currentSessionId = ref<string>('')
  const loading = ref(false)
  const error = ref<string | null>(null)
  const sessions = ref<ChatSession[]>([])
  const streamingStatus = ref<string>('')

  const messageCount = computed(() => messages.value.length)
  const lastMessage = computed(() => messages.value[messages.value.length - 1] || null)
  const hasError = computed(() => error.value !== null)

  function generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  function addMessage(role: Message['role'], content: string, type: Message['type'] = 'text', sources?: Source[]): Message {
    const message: Message = {
      id: generateId(),
      role,
      type,
      content,
      sources,
      timestamp: Date.now(),
    }
    messages.value.push(message)
    cacheLocally()
    return message
  }

  function updateMessage(id: string, updates: Partial<Message>): void {
    const index = messages.value.findIndex(m => m.id === id)
    if (index !== -1) {
      messages.value[index] = { ...messages.value[index], ...updates }
      cacheLocally()
    }
  }

  function removeMessage(id: string): void {
    const index = messages.value.findIndex(m => m.id === id)
    if (index !== -1) {
      messages.value.splice(index, 1)
      cacheLocally()
    }
  }

  function clearMessages(): void {
    messages.value = []
    streamingStatus.value = ''
    cacheLocally()
  }

  function startNewSession(): void {
    currentSessionId.value = generateId()
    messages.value = []
    streamingStatus.value = ''
    error.value = null
  }

  function cacheLocally(): void {
    try {
      const session = {
        id: currentSessionId.value,
        title: messages.value.find(m => m.role === 'user')?.content.slice(0, 30) || '新对话',
        messages: messages.value.slice(-50),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      const cached = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
      const idx = cached.findIndex((s: any) => s.id === session.id)
      if (idx >= 0) cached[idx] = session
      else cached.unshift(session)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(cached.slice(0, 20)))
    } catch { /* best-effort cache */ }
  }

  async function loadSessions(): Promise<void> {
    try {
      const res = await api.get('/chat/sessions')
      if (res.data?.sessions) {
        sessions.value = res.data.sessions.map((s: any) => ({
          id: s.id,
          title: s.title || '未命名对话',
          messages: [],
          created_at: s.created_at,
          updated_at: s.updated_at,
        }))
        return
      }
    } catch { /* fallback to localStorage */ }

    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        sessions.value = JSON.parse(stored)
      }
    } catch {
      sessions.value = []
    }
  }

  async function loadSession(sessionId: string): Promise<void> {
    try {
      const res = await api.get(`/chat/sessions/${sessionId}`)
      if (res.data?.messages) {
        currentSessionId.value = sessionId
        messages.value = res.data.messages
          .filter((m: any) => m.role !== 'system')
          .map((m: any, i: number) => ({
            id: `${sessionId}-${i}`,
            role: m.role,
            type: 'text' as const,
            content: m.content,
            sources: m.metadata?.sources || [],
            timestamp: new Date(m.created_at).getTime(),
          }))
        error.value = null
        cacheLocally()
        return
      }
    } catch { /* fallback */ }

    const session = sessions.value.find(s => s.id === sessionId)
    if (session) {
      currentSessionId.value = sessionId
      messages.value = [...session.messages]
      error.value = null
    }
  }

  async function deleteSession(sessionId: string): Promise<void> {
    try {
      await api.delete(`/chat/sessions/${sessionId}`)
    } catch { /* best-effort */ }

    const index = sessions.value.findIndex(s => s.id === sessionId)
    if (index !== -1) {
      sessions.value.splice(index, 1)
    }
    if (currentSessionId.value === sessionId) {
      startNewSession()
    }
  }

  async function sendMessage(
    query: string,
    options?: { knowledgeId?: string; model?: string; imageBase64?: string }
  ): Promise<void> {
    if (loading.value || !query.trim()) return

    loading.value = true
    error.value = null
    streamingStatus.value = '正在连接...'

    addMessage('user', query.trim())

    let assistantMsgId: string | null = null
    let statusMsgId: string | null = addMessage('system', '正在连接...', 'status').id

    try {
      await chatApi.streamChat(
        { query, knowledge_id: options?.knowledgeId, image_base64: options?.imageBase64 },
        {
          onMessage: (data: SSEData) => {
            switch (data.type) {
              case 'connected':
                streamingStatus.value = '已连接'
                if (statusMsgId) updateMessage(statusMsgId, { content: '已连接', statusLabel: '连接' })
                break

              case 'status':
                streamingStatus.value = data.content || ''
                if (statusMsgId) {
                  updateMessage(statusMsgId, { content: data.content || '', statusLabel: '状态' })
                }
                break

              case 'intent':
                streamingStatus.value = `意图识别: ${data.content}`
                if (statusMsgId) {
                  updateMessage(statusMsgId, { content: data.content || '', statusLabel: '意图识别' })
                }
                break

              case 'expansion':
                if (data.content && Array.isArray(data.content)) {
                  streamingStatus.value = `扩展查询: ${data.content.length} 个方向`
                  if (statusMsgId) {
                    updateMessage(statusMsgId, {
                      content: data.content.join(', '),
                      statusLabel: `扩展查询 (${data.content.length})`,
                    })
                  }
                }
                break

              case 'retrieval':
                streamingStatus.value = `检索到 ${data.count || 0} 个文档片段`
                if (statusMsgId) {
                  updateMessage(statusMsgId, {
                    content: `检索到 ${data.count || 0} 个相关文档`,
                    statusLabel: '文档检索',
                  })
                }
                break

              case 'rerank':
                streamingStatus.value = `重排序完成，保留 ${data.top_k || 0} 个结果`
                if (statusMsgId) {
                  updateMessage(statusMsgId, {
                    content: `重排序后保留前 ${data.top_k || 0} 个结果`,
                    statusLabel: '重排序',
                  })
                }
                break

              case 'answer':
                if (data.chunk) {
                  // Streaming chunk - build up assistant message
                  if (statusMsgId) {
                    removeMessage(statusMsgId)
                    statusMsgId = null
                  }
                  if (!assistantMsgId) {
                    const m = addMessage('assistant', '')
                    assistantMsgId = m.id
                  }
                  updateMessage(assistantMsgId, {
                    content: (messages.value.find(m => m.id === assistantMsgId)?.content || '') + (data.content || ''),
                  })
                  streamingStatus.value = '正在生成回答...'
                } else {
                  // Complete answer
                  if (statusMsgId) {
                    removeMessage(statusMsgId)
                    statusMsgId = null
                  }
                  if (!assistantMsgId) {
                    addMessage('assistant', data.content || '')
                  } else {
                    updateMessage(assistantMsgId, { content: data.content || '' })
                  }
                }
                break

              case 'source':
                if (data.source) {
                  const targetId = assistantMsgId || lastMessage.value?.id
                  if (targetId) {
                    const msg = messages.value.find(m => m.id === targetId)
                    if (msg && msg.role === 'assistant') {
                      if (!msg.sources) msg.sources = []
                      msg.sources.push(data.source)
                    }
                  }
                }
                break

              case 'evaluation':
                streamingStatus.value = '评估完成'
                if (statusMsgId) {
                  updateMessage(statusMsgId, { content: '质量评估完成', statusLabel: '评估' })
                }
                break

              case 'done':
                streamingStatus.value = ''
                if (statusMsgId) {
                  removeMessage(statusMsgId)
                  statusMsgId = null
                }
                assistantMsgId = null
                loading.value = false
                cacheLocally()
                break

              case 'error':
                error.value = data.content || '未知错误'
                streamingStatus.value = ''
                if (statusMsgId) {
                  removeMessage(statusMsgId)
                  statusMsgId = null
                }
                addMessage('system', data.content || '发生了错误', 'error')
                loading.value = false
                break
            }
          },
          onError: (err) => {
            error.value = err.message
            streamingStatus.value = ''
            if (statusMsgId) {
              removeMessage(statusMsgId)
              statusMsgId = null
            }
            addMessage('system', '抱歉，发生了错误，请稍后重试。', 'error')
            loading.value = false
          },
        }
      )
    } catch (err: any) {
      error.value = err.message || 'Failed to send message'
      loading.value = false
      addMessage('system', '抱歉，发生了错误，请稍后重试。', 'error')
    }
  }

  async function initialize(): Promise<void> {
    await loadSessions()
    if (!currentSessionId.value) {
      startNewSession()
    }
  }

  return {
    messages, currentSessionId, loading, error, sessions, streamingStatus,
    messageCount, lastMessage, hasError,
    addMessage, updateMessage, removeMessage, clearMessages,
    startNewSession, loadSession, deleteSession, sendMessage, initialize,
  }
})
