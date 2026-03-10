import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import GraphAggregateTable from '@/features/graph/components/GraphAggregateTable.vue'

describe('GraphAggregateTable', () => {
    it('emits the selected paper when a row is clicked', async () => {
        const paper = {
            id: 'paper-1',
            entry_id: 'entry-1',
            title: 'Flexible Computers',
            authors: ['Gerald Sussman'],
            venue: 'MIT',
            year: 2024,
            citation_count: 42,
            frequency: 3,
            in_library: true,
        }

        const wrapper = mount(GraphAggregateTable, {
            props: {
                title: 'Prior Works',
                description: 'desc',
                emptyLabel: 'empty',
                papers: [paper],
                formatAuthors: (authors: string[]) => authors.join(', '),
                formatCount: (value: number) => String(value),
            },
        })

        await wrapper.get('tbody tr').trigger('click')

        expect(wrapper.emitted('select-paper')).toEqual([[paper]])
    })
})
