import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const listEntityLabelsMock = vi.fn()
const listEntitiesMock = vi.fn()

vi.mock('@/api/client', () => ({
    api: {
        listEntityLabels: (...args: unknown[]) => listEntityLabelsMock(...args),
        listEntities: (...args: unknown[]) => listEntitiesMock(...args),
    },
    ApiError: class ApiError extends Error {},
}))

import NerEntityListView from '@/views/NerEntityList.vue'

function mountNerEntityList() {
    return mount(NerEntityListView, {
        global: {
            stubs: {
                AppShell: { template: '<div><slot name="actions" /><slot /></div>' },
                RouterLink: {
                    props: ['to'],
                    template: '<a :data-to="to"><slot /></a>',
                },
            },
        },
    })
}

describe('NerEntityList view', () => {
    beforeEach(() => {
        listEntityLabelsMock.mockReset()
        listEntitiesMock.mockReset()
    })

    it('loads labels and applies server-side label filtering', async () => {
        listEntityLabelsMock.mockResolvedValue([
            { label: 'method', entities: 2, paper_hits: 10 },
            { label: 'task', entities: 1, paper_hits: 5 },
        ])
        listEntitiesMock
            .mockResolvedValueOnce([
                {
                    canonical_id: 'ent-method',
                    canonical_surface: 'Method Entity',
                    label: 'method',
                    paper_hits: 10,
                    years_active: 2,
                },
            ])
            .mockResolvedValueOnce([
                {
                    canonical_id: 'ent-task',
                    canonical_surface: 'Task Entity',
                    label: 'task',
                    paper_hits: 5,
                    years_active: 1,
                },
            ])

        const wrapper = mountNerEntityList()
        await flushPromises()

        expect(listEntityLabelsMock).toHaveBeenCalledTimes(1)
        expect(listEntitiesMock).toHaveBeenNthCalledWith(
            1,
            50,
            0,
            'paper_hits',
            'desc',
            undefined,
        )
        expect(wrapper.text()).toContain('Method Entity')

        const taskButton = wrapper.findAll('button').find((b) => b.text() === 'task')
        expect(taskButton).toBeDefined()
        await taskButton!.trigger('click')
        await flushPromises()

        expect(listEntitiesMock).toHaveBeenNthCalledWith(
            2,
            50,
            0,
            'paper_hits',
            'desc',
            'task',
        )
        expect(wrapper.text()).toContain('Task Entity')
    })
})
