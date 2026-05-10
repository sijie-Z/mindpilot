/**
 * Shared API types for MindPilot frontend.
 * Single source of truth for all data models.
 */

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

export interface RetrievalConfig {
  vector_weight: number
  bm25_weight: number
  top_k: number
  rerank_enabled: boolean
  llm_model?: string
  embedding_model?: string
}

export interface SystemStats {
  total_queries: number
  avg_latency: number
  token_usage: string
  avg_score: number
  active_sessions: number
}

export interface KnowledgeListResponse {
  items: KnowledgeBase[]
  total: number
}

export interface DocumentListResponse {
  items: Document[]
  total: number
}

export interface UploadResponse {
  task_id: string
  filename: string
  status: string
  document?: Document
}
