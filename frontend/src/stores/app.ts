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
      // Use direct axios call without baseURL to hit /health directly
      const response = await axios.get('/health', { timeout: 5000 })
      backendOnline.value = response.status === 200
      return backendOnline.value
    } catch (err: any) {
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

  function clearError(): void {
    error.value = null
  }

  function initialize(): void {
    loadPreferences()
    checkBackendHealth()

    // Listen for system theme changes
    if (theme.value === 'auto') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      mediaQuery.addEventListener('change', applyTheme)
    }

    // Periodic health check (every 30 seconds)
    setInterval(() => {
      checkBackendHealth()
    }, 30000)
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
  }
})
