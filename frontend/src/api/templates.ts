import api from './index'

export interface PromptTemplate {
  id: string
  title: string
  content: string
  category: string
  is_builtin: boolean
  is_owner: boolean
}

export const templatesApi = {
  async list(category?: string): Promise<PromptTemplate[]> {
    const params = category ? { category } : {}
    const res = await api.get('/templates/', { params })
    return res.data.templates || []
  },

  async create(data: { title: string; content: string; category?: string }): Promise<{ id: string }> {
    const res = await api.post('/templates/', data)
    return res.data
  },

  async update(id: string, data: { title?: string; content?: string; category?: string }): Promise<void> {
    await api.put(`/templates/${id}`, data)
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/templates/${id}`)
  },
}
