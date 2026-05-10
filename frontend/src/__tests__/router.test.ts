/**
 * Tests for Vue Router configuration.
 * Verifies route definitions and navigation guards.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import router from '@/router/index'

describe('Router', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('has all expected routes', () => {
    const routeNames = router.getRoutes().map(r => r.name).filter(Boolean)
    expect(routeNames).toContain('Login')
    expect(routeNames).toContain('Chat')
    expect(routeNames).toContain('ChatHistory')
    expect(routeNames).toContain('Knowledge')
    expect(routeNames).toContain('KnowledgeDetail')
    expect(routeNames).toContain('Workflow')
    expect(routeNames).toContain('Admin')
    expect(routeNames).toContain('NotFound')
  })

  it('redirects root to /chat', () => {
    const rootRoute = router.getRoutes().find(r => r.path === '/')
    expect(rootRoute).toBeDefined()
    expect(rootRoute?.redirect).toBe('/chat')
  })

  it('login route does not require auth', () => {
    const loginRoute = router.getRoutes().find(r => r.path === '/login')
    expect(loginRoute?.meta?.requiresAuth).toBe(false)
  })

  it('chat route requires auth', () => {
    const chatRoute = router.getRoutes().find(r => r.path === '/chat')
    expect(chatRoute?.meta?.requiresAuth).toBe(true)
  })

  it('knowledge route requires auth', () => {
    const knowledgeRoute = router.getRoutes().find(r => r.path === '/knowledge')
    expect(knowledgeRoute?.meta?.requiresAuth).toBe(true)
  })

  it('admin route requires auth', () => {
    const adminRoute = router.getRoutes().find(r => r.path === '/admin')
    expect(adminRoute?.meta?.requiresAuth).toBe(true)
  })

  it('catch-all route matches any path', () => {
    const catchAllRoute = router.getRoutes().find(r => r.path === '/:pathMatch(.*)*')
    expect(catchAllRoute).toBeDefined()
    expect(catchAllRoute?.name).toBe('NotFound')
  })

  it('knowledge detail route accepts id param', () => {
    const detailRoute = router.getRoutes().find(r => r.path === '/knowledge/:id')
    expect(detailRoute).toBeDefined()
    expect(detailRoute?.props).toBeTruthy()
  })
})
