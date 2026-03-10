import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const route = reactive<{ query: Record<string, string> }>({ query: {} })
const router = { replace: vi.fn() }
const searchMock = vi.fn()

vi.mock('vue-router', () => ({
    useRoute: () => route,
    useRouter: () => router,
}))

vi.mock('@/api/client', () => ({
    api: {
        search: (...args: unknown[]) => searchMock(...args),
    },
}))

import SearchView from '@/views/Search.vue'

function mountSearch() {
    return mount(SearchView, {
        global: {
            stubs: {
                AppShell: { template: '<div><slot name="actions" /><slot /></div>' },
                RouterLink: { props: ['to'], template: '<a><slot /></a>' },
            },
        },
    })
}

describe('Search view', () => {
    beforeEach(() => {
        route.query = {}
        router.replace.mockReset()
        searchMock.mockReset()
        vi.useRealTimers()
    })

    it('renders the idle state without querying the backend', async () => {
        const wrapper = mountSearch()
        await flushPromises()

        expect(searchMock).not.toHaveBeenCalled()
        expect(wrapper.text()).toContain('Enter a search term to find papers')
    })

    it('renders degraded search results from the controller state', async () => {
        vi.useFakeTimers()
        route.query = { q: 'flexibility' }
        searchMock.mockResolvedValue({
            status: 'partial',
            warnings: [{ code: 'database_fallback', message: 'Using degraded database results.' }],
            hits: [
                {
                    id: 'entry-1',
                    title: 'Flexible Systems',
                    authors: ['Gerald Sussman'],
                    venue: 'MIT',
                    year: 2024,
                    has_pdf: true,
                    read: true,
                },
            ],
            total: 1,
        })

        const wrapper = mountSearch()
        await flushPromises()
        await vi.runAllTimersAsync()
        await flushPromises()

        expect(searchMock).toHaveBeenCalled()
        expect(wrapper.text()).toContain('Using degraded database results.')
        expect(wrapper.text()).toContain('Flexible Systems')
        expect(wrapper.text()).toContain('1 results')
    })
})
