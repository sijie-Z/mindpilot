import api from './index'
import type { RetrievalConfig, SystemStats } from './types'

export type { RetrievalConfig, SystemStats }

export interface SkillLiveData {
  call_count: number
  success_rate: number
  avg_latency_ms: number
}

export interface SkillHistoricalData {
  total_calls_30d: number
  avg_success_rate_30d: number
}

export interface SkillStats {
  [skillName: string]: {
    live: SkillLiveData
    historical: SkillHistoricalData
  }
}

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

  async getSkillStats(): Promise<SkillStats> {
    const response = await api.get('/admin/skill-stats')
    return response.data?.skills || {}
  },
}

export default adminApi
