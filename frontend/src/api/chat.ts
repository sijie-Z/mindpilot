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
  content?: string | string[]
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
   * Includes timeout protection to prevent loading state from getting stuck.
   */
  streamChat(message: ChatMessage, handlers: ChatHandlers): StreamController {
    const controller = new AbortController()
    let timeoutId: ReturnType<typeof setTimeout> | null = null
    let isCompleted = false

    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    // Reset timeout on any activity
    const resetTimeout = () => {
      if (timeoutId) clearTimeout(timeoutId)
      timeoutId = setTimeout(() => {
        if (!isCompleted) {
          isCompleted = true
          controller.abort()
          handlers.onError?.(new Error('请求超时，请重试'))
        }
      }, 120000) // 2 minute timeout
    }

    ;(async () => {
      resetTimeout()
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

            resetTimeout() // Reset timeout on data receive
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
          if ((error as Error).name === 'AbortError') {
            if (!isCompleted) {
              isCompleted = true
              handlers.onError?.(new Error('请求已取消'))
            }
            return
          }
          throw error
        }
      } catch (error) {
        if (!isCompleted) {
          isCompleted = true
          if ((error as Error).name === 'AbortError') return
          handlers.onError?.(error as Error)
        }
      } finally {
        if (timeoutId) clearTimeout(timeoutId)
      }
    })()

    return {
      abort: () => {
        isCompleted = true
        if (timeoutId) clearTimeout(timeoutId)
        controller.abort()
      }
    }
  },

  async chat(message: ChatMessage): Promise<unknown> {
    const response = await api.post('/chat/', message)
    return response.data
  },

  /**
   * Export a chat session as a file download.
   * @param sessionId - The session to export
   * @param format - 'markdown' or 'json'
   */
  async exportSession(sessionId: string, format: 'markdown' | 'json' = 'markdown'): Promise<void> {
    const token = localStorage.getItem('token')
    const headers: Record<string, string> = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(`/api/chat/sessions/${sessionId}/export?format=${format}`, {
      method: 'GET',
      headers,
    })

    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`)
    }

    // Trigger file download
    const blob = await response.blob()
    const ext = format === 'json' ? 'json' : 'md'
    const filename = `chat_${sessionId.slice(0, 8)}.${ext}`

    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },

  /**
   * Create a share link for a session.
   */
  async shareSession(sessionId: string): Promise<{ share_id: string; url: string }> {
    const response = await api.post(`/chat/sessions/${sessionId}/share`)
    return response.data
  },

  /**
   * Remove share link for a session.
   */
  async unshareSession(sessionId: string): Promise<void> {
    await api.delete(`/chat/sessions/${sessionId}/share`)
  },

  /**
   * Get shared session by share ID.
   */
  async getSharedSession(shareId: string): Promise<Record<string, unknown>> {
    const response = await api.get(`/chat/share/${shareId}`)
    return response.data
  },
}

export default chatApi
