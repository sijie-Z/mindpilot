import api from './index'
import type { RetrievalConfig, SystemStats } from './types'

export type { RetrievalConfig, SystemStats }

export const adminApi = {
  async getRetrievalConfig(): Promise<RetrievalConfig> {
    const response = await api.get('/knowledge/retrieval-config/config')
    return response.data
  },

  async updateRetrievalConfig(config: Partial<RetrievalConfig>): Promise<RetrievalConfig> {
    const response = await api.put('/knowledge/retrieval-config/config', config)
    return response.data
  },

  async getSystemStats(): Promise<SystemStats> {
    const response = await api.get('/knowledge/stats/overview')
    return response.data
  },
}

export default adminApi
