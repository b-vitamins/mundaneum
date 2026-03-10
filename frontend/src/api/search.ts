import { client, handleError, withRetry } from '@/api/base'
import type { SearchQueryInput, SearchResponse } from '@/api/types'

function buildSortParam(query: SearchQueryInput): string | undefined {
    if (!query.sort) {
        return undefined
    }
    return `${query.sort.field}:${query.sort.order}`
}

function buildSearchParams(query: SearchQueryInput): Record<string, string | number | boolean | undefined> {
    return {
        q: query.query,
        ...query.filters,
        limit: query.limit,
        offset: query.offset,
        sort: buildSortParam(query),
    }
}

export const searchApi = {
    async search(query: SearchQueryInput): Promise<SearchResponse> {
        try {
            const { data } = await withRetry(() =>
                client.get('/search', {
                    params: buildSearchParams(query),
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },
}
