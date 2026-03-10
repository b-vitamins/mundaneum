import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const route = reactive<{ query: Record<string, string> }>({ query: {} })
const router = { replace: vi.fn() }
const listSubjectsMock = vi.fn()

vi.mock('vue-router', () => ({
    useRoute: () => route,
    useRouter: () => router,
}))

vi.mock('@/api/client', () => ({
    api: {
        listAuthors: vi.fn(),
        listTopics: vi.fn(),
        listVenues: vi.fn(),
        listSubjects: (...args: unknown[]) => listSubjectsMock(...args),
    },
}))

import CatalogListPage from '@/views/CatalogListPage.vue'

describe('Catalog list page', () => {
    beforeEach(() => {
        route.query = {}
        router.replace.mockReset()
        listSubjectsMock.mockReset()
    })

    it('renders grouped subject cards through the adapter registry', async () => {
        listSubjectsMock.mockResolvedValue([
            {
                id: '1',
                slug: 'machine-learning',
                name: 'Machine Learning',
                display_name: 'Machine Learning',
                parent_slug: 'computer-science',
                entry_count: 12,
            },
            {
                id: '2',
                slug: 'logic',
                name: 'Logic',
                display_name: 'Logic',
                parent_slug: 'mathematics',
                entry_count: 7,
            },
        ])

        const wrapper = mount(CatalogListPage, {
            props: { entity: 'subjects' },
            global: {
                stubs: {
                    AppShell: { template: '<div><slot name="actions" /><slot /></div>' },
                    RouterLink: { props: ['to'], template: '<a><slot /></a>' },
                },
            },
        })

        await flushPromises()

        expect(listSubjectsMock).toHaveBeenCalledWith(200, 0, 'name', 'asc')
        expect(wrapper.text()).toContain('Computer Science')
        expect(wrapper.text()).toContain('Machine Learning')
        expect(wrapper.text()).toContain('12')
    })
})
