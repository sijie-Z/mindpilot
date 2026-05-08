import api from './index'

export interface ChatMessage {
  query: string
  session_id?: string
  knowledge_id?: string
  knowledge_base_ids?: string[]
  image_base64?: string
}

export interface SSEData {
  type: 'connected' | 'status' | 'intent' | 'expansion' | 'retrieval' | 'rerank' | 'answer' | 'source' | 'evaluation' | 'done' | 'error'
  content?: string
  chunk?: boolean
  count?: number
  top_k?: number
  source?: Record<string, unknown>
  data?: Record<string, unknown>
  latency_ms?: number
}

export interface ChatHandlers {
  onMessage: (data: SSEData) => void
  onError?: (error: Error) => void
}

export interface StreamController {
  abort: () => void
}

export const chatApi = {
  /**
   * Start a streaming chat request. Returns a controller to abort the stream.
   */
  streamChat(message: ChatMessage, handlers: ChatHandlers): StreamController {
    const controller = new AbortController()

    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    ;(async () => {
      try {
        const response = await fetch('/api/chat/stream', {
          method: 'POST',
          headers,
          body: JSON.stringify(message),
          signal: controller.signal,
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
                } catch {
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
            } catch {
              // Ignore
            }
          }
        } catch (error) {
          if ((error as Error).name === 'AbortError') return
          handlers.onError?.(error as Error)
          throw error
        }
      } catch (error) {
        if ((error as Error).name === 'AbortError') return
        handlers.onError?.(error as Error)
      }
    })()

    return { abort: () => controller.abort() }
  },

  async chat(message: ChatMessage): Promise<unknown> {
    const response = await api.post('/chat/', message)
    return response.data
  },
}

export default chatApi
