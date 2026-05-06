import api from './index'

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  status: 'active' | 'inactive' | 'processing' | 'error'
  embedding_model: string
  chunk_strategy: string
  chunk_size: number
  chunk_overlap: number
  doc_count: number
  chunk_count: number
  document_count: number
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

export interface UploadResponse {
  task_id: string
  filename: string
  status: string
  document?: Document
}

export interface KnowledgeListResponse {
  items: KnowledgeBase[]
  total: number
}

export interface DocumentListResponse {
  items: Document[]
  total: number
}

export interface RetrievalConfig {
  vector_weight: number
  bm25_weight: number
  top_k: number
  rerank_enabled: boolean
}

export const knowledgeApi = {
  async list(): Promise<KnowledgeListResponse> {
    try {
      const response = await api.get('/knowledge/')
      return { items: response.data, total: response.data.length }
    } catch {
      return { items: [], total: 0 }
    }
  },

  // Alias for compatibility
  async listKnowledgeBases(): Promise<KnowledgeBase[]> {
    const result = await this.list()
    return result.items
  },

  async createKnowledgeBase(data: { name: string; description?: string }): Promise<KnowledgeBase> {
    return this.create(data)
  },

  async deleteKnowledgeBase(id: string): Promise<void> {
    return this.delete(id)
  },

  async uploadDocument(knowledgeId: string, file: File, onProgress?: (p: number) => void): Promise<Document> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('knowledge_id', knowledgeId)

    const response = await api.post('/document/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total))
        }
      },
    })
    return response.data.document || response.data
  },

  async get(id: string): Promise<KnowledgeBase> {
    const response = await api.get(`/knowledge/${id}`)
    return response.data
  },

  async create(data: Partial<KnowledgeBase>): Promise<KnowledgeBase> {
    const response = await api.post('/knowledge/', data)
    return response.data
  },

  async update(id: string, data: Partial<KnowledgeBase>): Promise<KnowledgeBase> {
    const response = await api.put(`/knowledge/${id}`, data)
    return response.data
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/knowledge/${id}`)
  },

  async getRetrievalConfig(): Promise<RetrievalConfig> {
    try {
      const response = await api.get('/knowledge/retrieval-config/config')
      return response.data
    } catch {
      return {
        vector_weight: 0.7,
        bm25_weight: 0.3,
        top_k: 10,
        rerank_enabled: true,
      }
    }
  },

  async updateRetrievalConfig(config: Partial<RetrievalConfig>): Promise<RetrievalConfig> {
    const response = await api.put('/knowledge/retrieval-config/config', config)
    return response.data
  },
}

export const documentApi = {
  async list(knowledgeBaseId: string): Promise<DocumentListResponse> {
    try {
      const response = await api.get(`/knowledge/${knowledgeBaseId}/documents`)
      return { items: response.data, total: response.data.length }
    } catch {
      return { items: [], total: 0 }
    }
  },

  async upload(knowledgeId: string, file: File): Promise<Document> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('knowledge_id', knowledgeId)

    const response = await api.post('/document/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data.document || response.data
  },

  async delete(documentId: string): Promise<void> {
    await api.delete(`/document/${documentId}`)
  },

  async get(documentId: string): Promise<Document> {
    const response = await api.get(`/document/${documentId}`)
    return response.data
  },

  async reprocess(documentId: string): Promise<void> {
    await api.post(`/document/${documentId}/reprocess`)
  },
}

export default { knowledgeApi, documentApi }
