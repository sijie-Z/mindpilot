import api from './index'

export interface RetrievalConfig {
  vector_weight: number
  bm25_weight: number
  top_k: number
  rerank_enabled: boolean
}

export interface SystemStats {
  total_queries: number
  avg_latency: number
  token_usage: string
  avg_score: number
  active_sessions: number
}

export const adminApi = {
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

  async getSystemStats(): Promise<SystemStats> {
    try {
      const response = await api.get('/knowledge/stats/overview')
      return response.data
    } catch {
      return {
        total_queries: 0,
        avg_latency: 0,
        token_usage: '0',
        avg_score: 0,
        active_sessions: 0,
      }
    }
  },
}

export default adminApi