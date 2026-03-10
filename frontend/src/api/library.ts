import { client, handleError, withRetry } from '@/api/base'
import type {
    EntryDetail,
    EntryListItem,
    GraphData,
    S2Meta,
    S2Paper,
    Stats,
} from '@/api/types'

export const libraryApi = {
    async getStats(): Promise<Stats> {
        try {
            const { data } = await withRetry(() => client.get('/stats'))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async listEntries(limit = 50, offset = 0, sortBy = 'created_at', sortOrder = 'desc'): Promise<EntryListItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get('/entries', {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },
    async getEntry(id: string): Promise<EntryDetail> {
        try {
            const { data } = await withRetry(() => client.get(`/entries/${id}`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getEntryS2(id: string): Promise<S2Meta> {
        try {
            const { data } = await withRetry(() => client.get(`/entries/${id}/s2`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async toggleRead(id: string, read: boolean): Promise<void> {
        try {
            await withRetry(() => client.patch(`/entries/${id}/read`, { read }))
        } catch (error) {
            return handleError(error)
        }
    },

    async updateNotes(id: string, notes: string): Promise<void> {
        try {
            await withRetry(() => client.patch(`/entries/${id}/notes`, { notes }))
        } catch (error) {
            return handleError(error)
        }
    },

    async getBibtex(id: string): Promise<string> {
        try {
            const { data } = await withRetry(() => client.get(`/entries/${id}/bibtex`))
            return typeof data === 'string' ? data : data.bibtex
        } catch (error) {
            return handleError(error)
        }
    },

    async getCitations(id: string): Promise<S2Paper[]> {
        try {
            const { data } = await withRetry(() => client.get(`/entries/${id}/citations`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getReferences(id: string): Promise<S2Paper[]> {
        try {
            const { data } = await withRetry(() => client.get(`/entries/${id}/references`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getGraph(entryId: string, depth = 1, maxNodes = 80): Promise<GraphData> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/graph/${entryId}`, {
                    params: { depth, max_nodes: maxNodes },
                    timeout: 120000,
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },
}
