import { client, handleError, withRetry } from '@/api/base'

export interface NerEntityListItem {
    canonical_id: string
    canonical_surface: string
    label: string
    paper_hits: number
    years_active: number
}

export interface NerEntityLabelStat {
    label: string
    entities: number
    paper_hits: number
}

export interface NerEntityDetail {
    canonical_id: string
    canonical_surface: string
    label: string
    first_year: number | null
    last_year: number | null
    paper_hits: number
    mention_total: number
    venue_count: number
    venues: string[]
    years_active: number
}

export interface NerEntityEntryItem {
    id: string
    citation_key: string
    title: string
    year: number | null
    authors: string[]
    venue: string | null
    confidence: number
    mention_count: number
}

export interface EntryNerFact {
    canonical_id: string
    canonical_surface: string
    label: string
    confidence: number
    mention_count: number
}

export const nerApi = {
    async listEntityLabels(): Promise<NerEntityLabelStat[]> {
        try {
            const { data } = await withRetry(() => client.get('/ner/labels'))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async listEntities(
        limit = 100,
        offset = 0,
        sortBy = 'paper_hits',
        sortOrder = 'desc',
        label?: string,
    ): Promise<NerEntityListItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get('/ner/entities', {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder, label },
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getEntity(canonicalId: string): Promise<NerEntityDetail> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/ner/entities/${canonicalId}`)
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getEntityEntries(
        canonicalId: string,
        limit = 50,
        offset = 0,
        sortBy = 'year',
        sortOrder = 'desc',
    ): Promise<NerEntityEntryItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/ner/entities/${canonicalId}/entries`, {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder },
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getEntryEntities(entryId: string): Promise<EntryNerFact[]> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/ner/entries/${entryId}`)
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },
}
