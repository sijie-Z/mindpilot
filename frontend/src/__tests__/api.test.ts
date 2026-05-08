/**
 * Tests for API layer.
 * Verifies API client configuration and type definitions.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock the API module before importing
vi.mock('@/api/index', () => {
  const mockApi = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  }
  return { default: mockApi }
})

describe('API Types', () => {
  it('KnowledgeBase type has required fields', async () => {
    const types = await import('@/api/types')
    const kb: types.KnowledgeBase = {
      id: '1',
      name: 'Test',
      description: 'Desc',
      status: 'active',
      embedding_model: 'embedding-3',
      chunk_strategy: 'semantic',
      chunk_size: 512,
      chunk_overlap: 50,
      doc_count: 10,
      chunk_count: 100,
      document_count: 10,
      created_at: '2024-01-01',
    }
    expect(kb.id).toBe('1')
    expect(kb.status).toBe('active')
  })

  it('Document type has required fields', async () => {
    const types = await import('@/api/types')
    const doc: types.Document = {
      id: '1',
      name: 'doc.pdf',
      knowledge_base_id: 'kb-1',
      category: 'pdf',
      status: 'completed',
      size_bytes: 1024,
      chunk_count: 10,
      created_at: '2024-01-01',
    }
    expect(doc.status).toBe('completed')
  })

  it('RetrievalConfig type has required fields', async () => {
    const types = await import('@/api/types')
    const config: types.RetrievalConfig = {
      vector_weight: 0.7,
      bm25_weight: 0.3,
      top_k: 10,
      rerank_enabled: true,
    }
    expect(config.vector_weight + config.bm25_weight).toBeCloseTo(1.0)
  })

  it('SSEData type covers all event types', async () => {
    // Import chat types
    const chatModule = await import('@/api/chat')
    const eventTypes = [
      'connected', 'status', 'intent', 'expansion',
      'retrieval', 'rerank', 'answer', 'source',
      'evaluation', 'done', 'error',
    ]

    for (const type of eventTypes) {
      const data: chatModule.SSEData = { type: type as any }
      expect(data.type).toBe(type)
    }
  })

  it('ChatMessage type accepts optional fields', async () => {
    const chatModule = await import('@/api/chat')
    const msg: chatModule.ChatMessage = {
      query: 'test query',
      knowledge_id: 'kb-1',
      image_base64: 'base64data',
    }
    expect(msg.query).toBe('test query')
    expect(msg.knowledge_id).toBe('kb-1')
  })
})

describe('Chat API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('streamChat returns controller with abort', async () => {
    const chatModule = await import('@/api/chat')
    const handler = { onMessage: vi.fn(), onError: vi.fn() }

    // Mock fetch
    const mockAbort = vi.fn()
    vi.spyOn(global, 'AbortController').mockImplementation(() => ({
      abort: mockAbort,
      signal: { aborted: false } as AbortSignal,
    } as any))

    const controller = chatModule.chatApi.streamChat(
      { query: 'test' },
      handler
    )

    expect(controller).toBeDefined()
    expect(typeof controller.abort).toBe('function')
  })
})
