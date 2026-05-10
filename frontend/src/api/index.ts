import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: retry on transient errors + normalize errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      localStorage.removeItem('user_id')
      window.dispatchEvent(new CustomEvent('auth:logout'))
      return Promise.reject(error)
    }

    // Auto-retry on network errors and 502/503/504 (transient)
    const config = error.config
    const retryCount = config.__retryCount || 0
    const shouldRetry = (
      !error.response && error.code !== 'ECONNABORTED'  // network error
      || error.response?.status === 502
      || error.response?.status === 503
      || error.response?.status === 504
    )
    if (shouldRetry && retryCount < 2) {
      config.__retryCount = retryCount + 1
      await new Promise(r => setTimeout(r, 1000 * retryCount))  // 0s, 1s backoff
      return api(config)
    }

    return Promise.reject(error)
  }
)

export default api
