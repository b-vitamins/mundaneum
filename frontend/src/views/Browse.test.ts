import { reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const route = reactive<{ query: Record<string, string> }>({ query: {} })
const router = { replace: vi.fn() }
const listEntriesMock = vi.fn()

vi.mock('vue-router', () => ({
    useRoute: () => route,
    useRouter: () => router,
}))

vi.mock('@/api/client', () => ({
    api: {
        listEntries: (...args: unknown[]) => listEntriesMock(...args),
    },
}))

import BrowseView from '@/views/Browse.vue'

function mountBrowse() {
    return mount(BrowseView, {
        global: {
            stubs: {
                AppShell: { template: '<div><slot name="actions" /><slot /></div>' },
                RouterLink: {
                    props: ['to'],
                    template: '<a :data-to="JSON.stringify(to)"><slot /></a>',
                },
            },
        },
    })
}

describe('Browse view', () => {
    beforeEach(() => {
        route.query = {}
        router.replace.mockReset()
        listEntriesMock.mockReset()
    })

    it('renders the total count and author links from the entry payload', async () => {
        listEntriesMock.mockResolvedValue({
            items: [
                {
                    id: 'entry-1',
                    citation_key: 'paper-1',
                    entry_type: 'article',
                    title: 'Linked Authors',
                    year: 2024,
                    authors: ['Ada Lovelace'],
                    author_refs: [{ id: 'author-1', name: 'Ada Lovelace' }],
                    venue: 'Analytical Engine',
                    abstract: null,
                    file_path: null,
                    read: false,
                },
            ],
            total: 1,
        })

        const wrapper = mountBrowse()
        await flushPromises()

        expect(listEntriesMock).toHaveBeenCalledWith(50, 0, 'created_at', 'desc', {})
        expect(wrapper.text()).toContain('Showing 1 of 1 entries')
        expect(wrapper.text()).toContain('Linked Authors')
        expect(wrapper.text()).toContain('Ada Lovelace')
        expect(wrapper.html()).toContain('author-detail')
    })
})
