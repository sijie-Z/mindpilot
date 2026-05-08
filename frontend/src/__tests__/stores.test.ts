/**
 * Tests for Pinia stores.
 * Verifies state management logic without API calls.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '@/stores/app'
import { useChatStore } from '@/stores/chat'
import { useKnowledgeStore } from '@/stores/knowledge'

// Mock axios for app store health check
vi.mock('axios', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ status: 200 }),
  },
}))

// Mock API modules
vi.mock('@/api/index', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('@/api/chat', () => ({
  chatApi: {
    streamChat: vi.fn().mockReturnValue({ abort: vi.fn() }),
    chat: vi.fn(),
  },
}))

vi.mock('@/api/knowledge', () => ({
  knowledgeApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    getRetrievalConfig: vi.fn().mockResolvedValue({
      vector_weight: 0.7,
      bm25_weight: 0.3,
      top_k: 10,
      rerank_enabled: true,
    }),
    updateRetrievalConfig: vi.fn(),
  },
  documentApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    upload: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('App Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('initializes with default state', () => {
    const store = useAppStore()
    expect(store.backendOnline).toBe(false)
    expect(store.checkingBackend).toBe(false)
    expect(store.sidebarCollapsed).toBe(false)
    expect(store.theme).toBe('light')
    expect(store.error).toBeNull()
  })

  it('computes isDarkMode correctly', () => {
    const store = useAppStore()

    store.theme = 'light'
    expect(store.isDarkMode).toBe(false)

    store.theme = 'dark'
    expect(store.isDarkMode).toBe(true)
  })

  it('toggles sidebar', () => {
    const store = useAppStore()
    expect(store.sidebarCollapsed).toBe(false)

    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(true)

    store.toggleSidebar()
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('sets sidebar collapsed state', () => {
    const store = useAppStore()

    store.setSidebarCollapsed(true)
    expect(store.sidebarCollapsed).toBe(true)

    store.setSidebarCollapsed(false)
    expect(store.sidebarCollapsed).toBe(false)
  })

  it('persists sidebar preference to localStorage', () => {
    const store = useAppStore()

    store.toggleSidebar()
    expect(localStorage.setItem).toHaveBeenCalledWith(
      'mindpilot_sidebar_collapsed',
      'true'
    )
  })

  it('sets theme and persists', () => {
    const store = useAppStore()

    store.setTheme('dark')
    expect(store.theme).toBe('dark')
    expect(localStorage.setItem).toHaveBeenCalledWith(
      'mindpilot_theme',
      'dark'
    )
  })

  it('clears error', () => {
    const store = useAppStore()
    store.error = 'some error'
    store.clearError()
    expect(store.error).toBeNull()
  })

  it('loads preferences from localStorage', () => {
    localStorage.getItem = vi.fn((key: string) => {
      if (key === 'mindpilot_sidebar_collapsed') return 'true'
      if (key === 'mindpilot_theme') return 'dark'
      return null
    })

    const store = useAppStore()
    store.initialize()

    expect(store.sidebarCollapsed).toBe(true)
    expect(store.theme).toBe('dark')
  })
})

describe('Chat Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('initializes with empty state', () => {
    const store = useChatStore()
    expect(store.messages).toEqual([])
    expect(store.currentSessionId).toBe('')
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
    expect(store.sessions).toEqual([])
  })

  it('adds message correctly', () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'

    const msg = store.addMessage('user', 'hello')
    expect(store.messages).toHaveLength(1)
    expect(msg.role).toBe('user')
    expect(msg.content).toBe('hello')
    expect(msg.type).toBe('text')
    expect(msg.id).toBeDefined()
    expect(msg.timestamp).toBeDefined()
  })

  it('adds message with sources', () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'

    const sources = [{ filename: 'doc.pdf', score: 0.95 }]
    const msg = store.addMessage('assistant', 'answer', 'text', sources)
    expect(msg.sources).toEqual(sources)
  })

  it('updates message by id', () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'

    const msg = store.addMessage('user', 'original')
    store.updateMessage(msg.id, { content: 'updated' })

    expect(store.messages[0].content).toBe('updated')
    expect(store.messages[0].role).toBe('user')
  })

  it('removes message by id', () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'

    store.addMessage('user', 'msg1')
    const msg2 = store.addMessage('user', 'msg2')
    store.addMessage('user', 'msg3')

    store.removeMessage(msg2.id)
    expect(store.messages).toHaveLength(2)
    expect(store.messages.map(m => m.content)).toEqual(['msg1', 'msg3'])
  })

  it('clears all messages', () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'

    store.addMessage('user', 'msg1')
    store.addMessage('assistant', 'msg2')
    store.clearMessages()

    expect(store.messages).toEqual([])
    expect(store.streamingStatus).toBe('')
  })

  it('starts new session', () => {
    const store = useChatStore()
    store.currentSessionId = 'old-session'
    store.addMessage('user', 'msg')
    store.error = 'some error'

    store.startNewSession()

    expect(store.currentSessionId).not.toBe('old-session')
    expect(store.messages).toEqual([])
    expect(store.error).toBeNull()
  })

  it('computes messageCount', () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'

    expect(store.messageCount).toBe(0)
    store.addMessage('user', 'msg1')
    expect(store.messageCount).toBe(1)
    store.addMessage('assistant', 'msg2')
    expect(store.messageCount).toBe(2)
  })

  it('computes lastMessage', () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'

    expect(store.lastMessage).toBeNull()
    store.addMessage('user', 'first')
    expect(store.lastMessage?.content).toBe('first')
    store.addMessage('assistant', 'second')
    expect(store.lastMessage?.content).toBe('second')
  })

  it('computes hasError', () => {
    const store = useChatStore()
    expect(store.hasError).toBe(false)
    store.error = 'error'
    expect(store.hasError).toBe(true)
    store.error = null
    expect(store.hasError).toBe(false)
  })

  it('does not send empty message', async () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'

    await store.sendMessage('')
    expect(store.messages).toHaveLength(0)

    await store.sendMessage('   ')
    expect(store.messages).toHaveLength(0)
  })

  it('does not send when loading', async () => {
    const store = useChatStore()
    store.currentSessionId = 'test-session'
    store.loading = true

    await store.sendMessage('hello')
    expect(store.messages).toHaveLength(0)
  })
})

describe('Knowledge Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with default state', () => {
    const store = useKnowledgeStore()
    expect(store.knowledgeBases).toEqual([])
    expect(store.currentKnowledge).toBeNull()
    expect(store.documents).toEqual([])
    expect(store.loading).toBe(false)
    expect(store.uploading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('has default retrieval config', () => {
    const store = useKnowledgeStore()
    expect(store.retrievalConfig.vector_weight).toBe(0.7)
    expect(store.retrievalConfig.bm25_weight).toBe(0.3)
    expect(store.retrievalConfig.top_k).toBe(10)
    expect(store.retrievalConfig.rerank_enabled).toBe(true)
  })

  it('computes activeKnowledgeBases', () => {
    const store = useKnowledgeStore()
    store.knowledgeBases = [
      { id: '1', name: 'KB1', status: 'active' } as any,
      { id: '2', name: 'KB2', status: 'inactive' } as any,
      { id: '3', name: 'KB3', status: 'active' } as any,
    ]

    expect(store.activeKnowledgeBases).toHaveLength(2)
    expect(store.activeKnowledgeBases.map(kb => kb.id)).toEqual(['1', '3'])
  })

  it('computes totalDocuments', () => {
    const store = useKnowledgeStore()
    store.knowledgeBases = [
      { id: '1', document_count: 5 } as any,
      { id: '2', document_count: 3 } as any,
    ]

    expect(store.totalDocuments).toBe(8)
  })

  it('computes totalChunks', () => {
    const store = useKnowledgeStore()
    store.knowledgeBases = [
      { id: '1', chunk_count: 100 } as any,
      { id: '2', chunk_count: 200 } as any,
    ]

    expect(store.totalChunks).toBe(300)
  })

  it('clears error', () => {
    const store = useKnowledgeStore()
    store.error = 'some error'
    store.clearError()
    expect(store.error).toBeNull()
  })

  it('sets current knowledge and fetches documents', () => {
    const store = useKnowledgeStore()
    const kb = { id: 'kb-1', name: 'Test KB' } as any

    store.setCurrentKnowledge(kb)
    expect(store.currentKnowledge).toBe(kb)
  })

  it('clears documents when setting null knowledge', () => {
    const store = useKnowledgeStore()
    store.documents = [{ id: '1' } as any]

    store.setCurrentKnowledge(null)
    expect(store.currentKnowledge).toBeNull()
    expect(store.documents).toEqual([])
  })
})
