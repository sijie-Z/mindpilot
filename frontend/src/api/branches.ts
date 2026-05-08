/**
 * Conversation branching API.
 * Allows users to explore different conversation paths.
 */
import api from './index'

export interface Branch {
  id: string
  name: string
  parent_message_id: string
  session_id: string
  message_count: number
  created_at: string
}

export interface BranchListResponse {
  session_id: string
  main_branch: { message_count: number }
  branches: Branch[]
}

export interface BranchDetail {
  branch: {
    id: string
    session_id: string
    parent_message_id: string
    name: string
    created_at: string
  }
  messages: Array<{
    id: string
    role: string
    content: string
    metadata: Record<string, unknown>
    created_at: string
  }>
}

export const branchesApi = {
  /**
   * Create a new branch from a specific message.
   */
  async create(sessionId: string, messageId: string, name?: string): Promise<Branch> {
    const response = await api.post('/branches/create', {
      session_id: sessionId,
      message_id: messageId,
      branch_name: name,
    })
    return response.data
  },

  /**
   * List all branches for a session.
   */
  async list(sessionId: string): Promise<BranchListResponse> {
    const response = await api.get(`/branches/list/${sessionId}`)
    return response.data
  },

  /**
   * Get branch details with messages.
   */
  async get(branchId: string): Promise<BranchDetail> {
    const response = await api.get(`/branches/${branchId}`)
    return response.data
  },

  /**
   * Switch to a different branch.
   */
  async switch(sessionId: string, branchId: string): Promise<BranchDetail> {
    const response = await api.post('/branches/switch', {
      session_id: sessionId,
      branch_id: branchId,
    })
    return response.data
  },

  /**
   * Delete a branch.
   */
  async delete(branchId: string): Promise<void> {
    await api.delete(`/branches/${branchId}`)
  },
}

export default branchesApi
