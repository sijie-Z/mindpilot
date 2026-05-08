/**
 * App store for MindPilot.
 * Manages global application state like backend connectivity, UI preferences.
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

const SIDEBAR_KEY = 'mindpilot_sidebar_collapsed'
const THEME_KEY = 'mindpilot_theme'

export type Theme = 'light' | 'dark' | 'auto'

export const useAppStore = defineStore('app', () => {
  // State
  const backendOnline = ref(false)
  const checkingBackend = ref(false)
  const sidebarCollapsed = ref(false)
  const theme = ref<Theme>('light')
  const error = ref<string | null>(null)

  // Internal state
  let _healthInterval: ReturnType<typeof setInterval> | null = null
  let _mediaQuery: MediaQueryList | null = null
  let _initialized = false

  // Computed
  const isDarkMode = computed(() => {
    if (theme.value === 'auto') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches
    }
    return theme.value === 'dark'
  })

  // Actions
  async function checkBackendHealth(): Promise<boolean> {
    checkingBackend.value = true
    error.value = null

    try {
      const response = await axios.get('/health', { timeout: 5000 })
      backendOnline.value = response.status === 200
      return backendOnline.value
    } catch (err: unknown) {
      backendOnline.value = false
      error.value = '无法连接到后端服务'
      console.warn('Backend health check failed:', err)
      return false
    } finally {
      checkingBackend.value = false
    }
  }

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
    persistPreferences()
  }

  function setSidebarCollapsed(collapsed: boolean): void {
    sidebarCollapsed.value = collapsed
    persistPreferences()
  }

  function setTheme(newTheme: Theme): void {
    theme.value = newTheme
    applyTheme()
    persistPreferences()
    setupMediaListener()
  }

  function applyTheme(): void {
    const isDark = isDarkMode.value
    document.documentElement.classList.toggle('dark', isDark)
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light')
  }

  function persistPreferences(): void {
    try {
      localStorage.setItem(SIDEBAR_KEY, JSON.stringify(sidebarCollapsed.value))
      localStorage.setItem(THEME_KEY, theme.value)
    } catch {
      console.warn('Failed to persist preferences')
    }
  }

  function loadPreferences(): void {
    try {
      const sidebar = localStorage.getItem(SIDEBAR_KEY)
      if (sidebar !== null) {
        sidebarCollapsed.value = JSON.parse(sidebar)
      }

      const savedTheme = localStorage.getItem(THEME_KEY) as Theme | null
      if (savedTheme) {
        theme.value = savedTheme
      }

      applyTheme()
    } catch {
      console.warn('Failed to load preferences')
    }
  }

  function setupMediaListener(): void {
    // Clean up previous listener
    if (_mediaQuery) {
      _mediaQuery.removeEventListener('change', applyTheme)
      _mediaQuery = null
    }
    // Add listener if auto theme
    if (theme.value === 'auto') {
      _mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      _mediaQuery.addEventListener('change', applyTheme)
    }
  }

  function clearError(): void {
    error.value = null
  }

  function initialize(): void {
    // Prevent double initialization
    if (_initialized) return
    _initialized = true

    loadPreferences()
    setupMediaListener()
    checkBackendHealth()

    // Periodic health check (every 30 seconds)
    _healthInterval = setInterval(() => {
      checkBackendHealth()
    }, 30000)
  }

  function cleanup(): void {
    if (_healthInterval) {
      clearInterval(_healthInterval)
      _healthInterval = null
    }
    if (_mediaQuery) {
      _mediaQuery.removeEventListener('change', applyTheme)
      _mediaQuery = null
    }
    _initialized = false
  }

  return {
    // State
    backendOnline,
    checkingBackend,
    sidebarCollapsed,
    theme,
    error,

    // Computed
    isDarkMode,

    // Actions
    checkBackendHealth,
    toggleSidebar,
    setSidebarCollapsed,
    setTheme,
    applyTheme,
    clearError,
    initialize,
    cleanup,
  }
})
