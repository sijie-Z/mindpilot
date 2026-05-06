import api from './index'

export interface ChatMessage {
  query: string
  session_id?: string
  knowledge_id?: string
  knowledge_base_ids?: string[]
}

export interface SSEData {
  type: 'connected' | 'status' | 'intent' | 'expansion' | 'retrieval' | 'rerank' | 'answer' | 'source' | 'evaluation' | 'done' | 'error'
  content?: string
  chunk?: boolean
  count?: number
  top_k?: number
  source?: any
  data?: any
  latency_ms?: number
}

export interface ChatHandlers {
  onMessage: (data: SSEData) => void
  onError?: (error: Error) => void
}

export const chatApi = {
  async streamChat(message: ChatMessage, handlers: ChatHandlers): Promise<void> {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(message),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('Response body is not readable')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Process complete lines
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              handlers.onMessage(data)
            } catch (e) {
              // Ignore parse errors for incomplete JSON
            }
          }
        }
      }

      // Process any remaining data in buffer
      if (buffer.startsWith('data: ')) {
        try {
          const data = JSON.parse(buffer.slice(6))
          handlers.onMessage(data)
        } catch (e) {
          // Ignore
        }
      }
    } catch (error) {
      handlers.onError?.(error as Error)
      throw error
    }
  },

  async chat(message: ChatMessage): Promise<any> {
    const response = await api.post('/chat/', message)
    return response.data
  },
}

export default chatApi