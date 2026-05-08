/**
 * Tests for Vue components.
 * Verifies component rendering and basic interactions.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'

// Mock API modules
vi.mock('@/api/index', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
}))

vi.mock('@/api/chat', () => ({
  chatApi: {
    streamChat: vi.fn().mockReturnValue({ abort: vi.fn() }),
    chat: vi.fn(),
  },
}))

vi.mock('@/api/knowledge', () => ({
  knowledgeApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  documentApi: {
    list: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    upload: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('SkeletonCard Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders with default props', async () => {
    // Dynamic import to avoid issues with module resolution
    const { default: SkeletonCard } = await import('@/components/SkeletonCard.vue')

    const wrapper = mount(SkeletonCard, {
      props: {
        type: 'card',
      },
    })

    expect(wrapper.exists()).toBe(true)
  })

  it('renders different types', async () => {
    const { default: SkeletonCard } = await import('@/components/SkeletonCard.vue')

    const types = ['card', 'list', 'table'] as const
    for (const type of types) {
      const wrapper = mount(SkeletonCard, {
        props: { type },
      })
      expect(wrapper.exists()).toBe(true)
    }
  })
})

describe('LoadingState Component', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders with default props', async () => {
    const { default: LoadingState } = await import('@/components/LoadingState.vue')

    const wrapper = mount(LoadingState, {
      props: {
        loading: true,
      },
    })

    expect(wrapper.exists()).toBe(true)
  })

  it('shows content when not loading', async () => {
    const { default: LoadingState } = await import('@/components/LoadingState.vue')

    const wrapper = mount(LoadingState, {
      props: {
        loading: false,
      },
      slots: {
        default: '<div class="content">Test Content</div>',
      },
    })

    expect(wrapper.find('.content').exists()).toBe(true)
  })
})

describe('NotFoundView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders 404 page', async () => {
    const { default: NotFoundView } = await import('@/views/NotFoundView.vue')

    const router = createRouter({
      history: createWebHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: NotFoundView }],
    })

    const wrapper = mount(NotFoundView, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('404')
  })
})
