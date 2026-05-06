/**
 * Knowledge store for MindPilot.
 * Manages knowledge bases, documents, and retrieval configuration.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { knowledgeApi, documentApi } from '@/api/knowledge'

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  status: 'active' | 'inactive' | 'processing' | 'error'
  embedding_model: string
  chunk_strategy: string
  chunk_size: number
  chunk_overlap: number
  document_count: number
  chunk_count: number
  created_at: string
  updated_at?: string
}

export interface Document {
  id: string
  name: string
  knowledge_base_id: string
  category: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  size_bytes: number
  chunk_count: number
  created_at: string
  processed_at?: string
  error_message?: string
}

export interface RetrievalConfig {
  vector_weight: number
  bm25_weight: number
  top_k: number
  rerank_enabled: boolean
}

export const useKnowledgeStore = defineStore('knowledge', () => {
  // State
  const knowledgeBases = ref<KnowledgeBase[]>([])
  const currentKnowledge = ref<KnowledgeBase | null>(null)
  const documents = ref<Document[]>([])
  const retrievalConfig = ref<RetrievalConfig>({
    vector_weight: 0.7,
    bm25_weight: 0.3,
    top_k: 10,
    rerank_enabled: true,
  })
  const loading = ref(false)
  const uploading = ref(false)
  const error = ref<string | null>(null)

  // Computed
  const activeKnowledgeBases = computed(() =>
    knowledgeBases.value.filter(kb => kb.status === 'active')
  )
  const totalDocuments = computed(() =>
    knowledgeBases.value.reduce((sum, kb) => sum + kb.document_count, 0)
  )
  const totalChunks = computed(() =>
    knowledgeBases.value.reduce((sum, kb) => sum + kb.chunk_count, 0)
  )

  // Actions
  async function fetchKnowledgeBases(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await knowledgeApi.list()
      knowledgeBases.value = response.items || []
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch knowledge bases'
      console.error('Failed to fetch knowledge bases:', err)
    } finally {
      loading.value = false
    }
  }

  async function fetchKnowledgeBase(id: string): Promise<KnowledgeBase | null> {
    loading.value = true
    error.value = null

    try {
      const kb = await knowledgeApi.get(id)
      currentKnowledge.value = kb
      return kb
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch knowledge base'
      console.error('Failed to fetch knowledge base:', err)
      return null
    } finally {
      loading.value = false
    }
  }

  async function createKnowledgeBase(data: Partial<KnowledgeBase>): Promise<KnowledgeBase | null> {
    loading.value = true
    error.value = null

    try {
      const kb = await knowledgeApi.create(data)
      knowledgeBases.value.unshift(kb)
      return kb
    } catch (err: any) {
      error.value = err.message || 'Failed to create knowledge base'
      console.error('Failed to create knowledge base:', err)
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateKnowledgeBase(id: string, data: Partial<KnowledgeBase>): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      const kb = await knowledgeApi.update(id, data)
      const index = knowledgeBases.value.findIndex(k => k.id === id)
      if (index !== -1) {
        knowledgeBases.value[index] = kb
      }
      if (currentKnowledge.value?.id === id) {
        currentKnowledge.value = kb
      }
      return true
    } catch (err: any) {
      error.value = err.message || 'Failed to update knowledge base'
      console.error('Failed to update knowledge base:', err)
      return false
    } finally {
      loading.value = false
    }
  }

  async function deleteKnowledgeBase(id: string): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      await knowledgeApi.delete(id)
      knowledgeBases.value = knowledgeBases.value.filter(kb => kb.id !== id)
      if (currentKnowledge.value?.id === id) {
        currentKnowledge.value = null
        documents.value = []
      }
      return true
    } catch (err: any) {
      error.value = err.message || 'Failed to delete knowledge base'
      console.error('Failed to delete knowledge base:', err)
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchDocuments(knowledgeBaseId: string): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await documentApi.list(knowledgeBaseId)
      documents.value = response.items || []
    } catch (err: any) {
      error.value = err.message || 'Failed to fetch documents'
      console.error('Failed to fetch documents:', err)
    } finally {
      loading.value = false
    }
  }

  async function uploadDocument(knowledgeBaseId: string, file: File): Promise<Document | null> {
    uploading.value = true
    error.value = null

    try {
      const doc = await documentApi.upload(knowledgeBaseId, file)
      documents.value.unshift(doc)
      // Update knowledge base document count
      const kbIndex = knowledgeBases.value.findIndex(kb => kb.id === knowledgeBaseId)
      if (kbIndex !== -1) {
        knowledgeBases.value[kbIndex].document_count++
      }
      return doc
    } catch (err: any) {
      error.value = err.message || 'Failed to upload document'
      console.error('Failed to upload document:', err)
      return null
    } finally {
      uploading.value = false
    }
  }

  async function deleteDocument(knowledgeBaseId: string, documentId: string): Promise<boolean> {
    loading.value = true
    error.value = null

    try {
      await documentApi.delete(documentId)
      documents.value = documents.value.filter(d => d.id !== documentId)
      // Update knowledge base document count
      const kbIndex = knowledgeBases.value.findIndex(kb => kb.id === knowledgeBaseId)
      if (kbIndex !== -1 && knowledgeBases.value[kbIndex].document_count > 0) {
        knowledgeBases.value[kbIndex].document_count--
      }
      return true
    } catch (err: any) {
      error.value = err.message || 'Failed to delete document'
      console.error('Failed to delete document:', err)
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchRetrievalConfig(): Promise<void> {
    try {
      const config = await knowledgeApi.getRetrievalConfig()
      retrievalConfig.value = config
    } catch (err: any) {
      console.warn('Failed to fetch retrieval config:', err)
    }
  }

  async function updateRetrievalConfig(config: Partial<RetrievalConfig>): Promise<boolean> {
    try {
      const updated = await knowledgeApi.updateRetrievalConfig(config)
      retrievalConfig.value = updated
      return true
    } catch (err: any) {
      error.value = err.message || 'Failed to update retrieval config'
      console.error('Failed to update retrieval config:', err)
      return false
    }
  }

  function setCurrentKnowledge(kb: KnowledgeBase | null): void {
    currentKnowledge.value = kb
    if (kb) {
      fetchDocuments(kb.id)
    } else {
      documents.value = []
    }
  }

  function clearError(): void {
    error.value = null
  }

  return {
    // State
    knowledgeBases,
    currentKnowledge,
    documents,
    retrievalConfig,
    loading,
    uploading,
    error,

    // Computed
    activeKnowledgeBases,
    totalDocuments,
    totalChunks,

    // Actions
    fetchKnowledgeBases,
    fetchKnowledgeBase,
    createKnowledgeBase,
    updateKnowledgeBase,
    deleteKnowledgeBase,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    fetchRetrievalConfig,
    updateRetrievalConfig,
    setCurrentKnowledge,
    clearError,
  }
})
