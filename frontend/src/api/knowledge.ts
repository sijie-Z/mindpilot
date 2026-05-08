import api from './index'
import type {
  KnowledgeBase,
  Document,
  KnowledgeListResponse,
  DocumentListResponse,
  RetrievalConfig,
} from './types'

export type { KnowledgeBase, Document, KnowledgeListResponse, DocumentListResponse, RetrievalConfig }

export const knowledgeApi = {
  async list(): Promise<KnowledgeListResponse> {
    const response = await api.get('/knowledge/')
    return { items: response.data, total: response.data.length }
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
    const response = await api.get('/knowledge/retrieval-config/config')
    return response.data
  },

  async updateRetrievalConfig(config: Partial<RetrievalConfig>): Promise<RetrievalConfig> {
    const response = await api.put('/knowledge/retrieval-config/config', config)
    return response.data
  },
}

export const documentApi = {
  async list(knowledgeBaseId: string): Promise<DocumentListResponse> {
    const response = await api.get(`/knowledge/${knowledgeBaseId}/documents`)
    return { items: response.data, total: response.data.length }
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
