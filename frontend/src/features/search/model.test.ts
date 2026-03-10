import { describe, expect, it } from 'vitest'

import {
    buildSearchFilters,
    buildSearchRouteQuery,
    defaultSearchFilters,
    readSearchQuery,
} from '@/features/search/model'

describe('search model helpers', () => {
    it('builds typed filters from ternary form state', () => {
        const filters = defaultSearchFilters()
        filters.entry_type = 'article'
        filters.year_from = 1990
        filters.has_pdf = 'true'
        filters.read = 'false'

        expect(buildSearchFilters(filters)).toEqual({
            entry_type: 'article',
            year_from: 1990,
            has_pdf: true,
            read: false,
        })
    })

    it('round-trips route query state', () => {
        const filters = defaultSearchFilters()
        filters.year_to = 2024
        filters.has_pdf = 'false'

        const routeQuery = buildSearchRouteQuery('flexible systems', filters)
        expect(routeQuery).toEqual({
            q: 'flexible systems',
            year_to: '2024',
            has_pdf: 'false',
        })

        expect(readSearchQuery(routeQuery)).toEqual({
            query: 'flexible systems',
            filters: {
                entry_type: '',
                year_from: null,
                year_to: 2024,
                has_pdf: 'false',
                read: '',
            },
        })
    })
})
