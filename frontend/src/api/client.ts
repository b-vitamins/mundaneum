import axios, { type AxiosError } from 'axios'
import { API_CONFIG, DEFAULTS } from '@/constants'

// Create axios instance
const client = axios.create({
    baseURL: API_CONFIG.BASE_URL,
    timeout: API_CONFIG.TIMEOUT,
})

// Retry logic with exponential backoff
async function withRetry<T>(fn: () => Promise<T>, retries: number = DEFAULTS.MAX_RETRIES): Promise<T> {
    try {
        return await fn()
    } catch (error) {
        const axiosError = error as AxiosError

        // Don't retry on 4xx errors
        if (axiosError.response && axiosError.response.status >= 400 && axiosError.response.status < 500) {
            throw error
        }

        if (retries > 0) {
            const delay = DEFAULTS.RETRY_DELAY_MS * Math.pow(2, DEFAULTS.MAX_RETRIES - retries)
            await new Promise(resolve => setTimeout(resolve, delay))
            return withRetry(fn, retries - 1)
        }
        throw error
    }
}

// Types
export interface Stats {
    entries: number
    authors: number
    collections: number
}

export interface EntryListItem {
    id: string
    citation_key: string
    entry_type: string
    title: string
    year: number | null
    authors: string[]
    venue: string | null
    abstract: string | null
    file_path: string | null
    read: boolean
}

export interface SearchHit {
    id: string
    citation_key: string
    entry_type: string
    title: string
    year: number | null
    authors: string[]
    venue: string
    abstract: string
    has_pdf: boolean
    read: boolean
}

export interface SearchResponse {
    hits: SearchHit[]
    total: number
    processing_time_ms: number
}

export interface EntryDetail {
    id: string
    citation_key: string
    entry_type: string
    title: string
    year: number | null
    authors: string[]
    venue: string | null
    abstract: string | null
    file_path: string | null
    read: boolean
    required_fields: Record<string, unknown>
    optional_fields: Record<string, unknown>
    notes: string | null
    source_file: string
}

export interface Collection {
    id: string
    name: string
    entry_count: number
}

export interface CollectionDetail extends Collection {
    description: string | null
    entries: Array<{
        id: string
        title: string
        year: number | null
        sort_order: number
    }>
}

export interface SearchFilters {
    entry_type?: string
    year_from?: number
    year_to?: number
    has_pdf?: boolean
    read?: boolean
}

export class ApiError extends Error {
    constructor(
        message: string,
        public status: number,
        public detail?: string
    ) {
        super(message)
        this.name = 'ApiError'
    }
}

export interface S2Paper {
    s2_id: string
    title: string
    year?: number
    venue?: string
    authors: { authorId: string; name: string }[]
    tldr?: { model: string; text: string }
    citation_count: number
    is_influential: boolean
    contexts: string[]
    intents: string[]
}

// Graph types
export interface GraphNode {
    id: string
    title: string
    year: number | null
    venue: string | null
    authors: string[]
    citation_count: number
    fields_of_study: string[]
    in_library: boolean
    entry_id: string | null
}

export interface GraphEdge {
    source: string
    target: string
    is_influential: boolean
}

export interface GraphData {
    center_id: string
    nodes: GraphNode[]
    edges: GraphEdge[]
}

// Admin API types
export interface AdminHealth {
    status: string
    database: string
    search: string
    bib_directory: string
    bib_files_count: number
}

export interface ExportedEntry {
    citation_key: string
    notes: string | null
    read: boolean
}

export interface ExportedCollection {
    name: string
    description: string | null
    sort_order: number
    entry_keys: string[]
}

export interface ExportData {
    version: string
    exported_at: string
    entries: ExportedEntry[]
    collections: ExportedCollection[]
}

export interface ImportResult {
    entries_updated: number
    entries_skipped: number
    collections_created: number
    collections_updated: number
    errors: string[]
}

// Author types
export interface AuthorListItem {
    id: string
    name: string
    entry_count: number
}

export interface AuthorDetail extends AuthorListItem { }

export interface AuthorEntryItem {
    id: string
    citation_key: string
    entry_type: string
    title: string
    year: number | null
    venue: string | null
    read: boolean
}

// Entity types (Venue, Subject, Topic)
export interface VenueListItem {
    id: string
    slug: string
    name: string
    category: string
    entry_count: number
}

export interface VenueDetail extends VenueListItem {
    aliases: string[]
    url?: string
}

export interface EntityEntryItem {
    id: string
    citation_key: string
    entry_type: string
    title: string
    year: number | null
    authors: string[]
    venue: string | null
    read: boolean
}

export interface SubjectListItem {
    id: string
    slug: string
    name: string
    parent_slug: string | null
    display_name: string | null
    entry_count: number
}

export interface SubjectDetail extends SubjectListItem { }

export interface TopicListItem {
    id: string
    slug: string
    name: string
    entry_count: number
}

export interface TopicDetail extends TopicListItem { }

// Error handler
function handleError(error: unknown): never {
    const axiosError = error as AxiosError<{ detail?: string }>
    if (axiosError.response) {
        throw new ApiError(
            axiosError.message,
            axiosError.response.status,
            axiosError.response.data?.detail
        )
    }
    throw new ApiError('Network error', 0)
}

// API methods
export const api = {
    async getStats(): Promise<Stats> {
        try {
            const { data } = await withRetry(() => client.get('/stats'))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async listEntries(
        limit = 50,
        offset = 0,
        sortBy = 'created_at',
        sortOrder = 'desc'
    ): Promise<EntryListItem[]> {
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

    async search(
        query: string,
        filters?: SearchFilters,
        limit = 20,
        offset = 0,
        sort?: string
    ): Promise<SearchResponse> {
        try {
            const { data } = await withRetry(() =>
                client.get('/search', {
                    params: { q: query, ...filters, limit, offset, sort }
                })
            )
            return data
        } catch {
            // Return empty results on error for graceful degradation
            return { hits: [], total: 0, processing_time_ms: 0 }
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
            // Backend now returns plain text
            return typeof data === 'string' ? data : data.bibtex
        } catch (error) {
            return handleError(error)
        }
    },

    async getCollections(): Promise<Collection[]> {
        try {
            const { data } = await withRetry(() => client.get('/collections'))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getCollection(id: string): Promise<CollectionDetail> {
        try {
            const { data } = await withRetry(() => client.get(`/collections/${id}`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async createCollection(name: string): Promise<Collection> {
        try {
            const { data } = await client.post('/collections', { name })
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async addToCollection(collectionId: string, entryId: string): Promise<void> {
        try {
            await client.post(`/collections/${collectionId}/entries/${entryId}`)
        } catch (error) {
            return handleError(error)
        }
    },

    async removeFromCollection(collectionId: string, entryId: string): Promise<void> {
        try {
            await client.delete(`/collections/${collectionId}/entries/${entryId}`)
        } catch (error) {
            return handleError(error)
        }
    },

    async deleteCollection(collectionId: string): Promise<void> {
        try {
            await client.delete(`/collections/${collectionId}`)
        } catch (error) {
            return handleError(error)
        }
    },

    async importBibtex(directory?: string): Promise<{ imported: number; errors: number; total_parsed: number }> {
        try {
            const { data } = await client.post('/ingest', { directory })
            return data
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

    // Graph API
    async getGraph(entryId: string, depth = 1, maxNodes = 80): Promise<GraphData> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/graph/${entryId}`, {
                    params: { depth, max_nodes: maxNodes }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    // Admin API methods
    async getAdminHealth(): Promise<AdminHealth> {
        try {
            const { data } = await withRetry(() => client.get('/admin/health'))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async exportBackup(): Promise<ExportData> {
        try {
            const { data } = await withRetry(() => client.get('/admin/export'))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async importBackup(backup: ExportData): Promise<ImportResult> {
        try {
            const { data } = await client.post('/admin/import', backup)
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async triggerIngest(directory?: string): Promise<{ imported: number; errors: number; total_parsed: number }> {
        try {
            const { data } = await client.post('/admin/ingest', { directory })
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    // Author API methods
    async listAuthors(
        limit = 100,
        offset = 0,
        sortBy = 'name',
        sortOrder = 'asc'
    ): Promise<AuthorListItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get('/authors', {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getAuthor(id: string): Promise<AuthorDetail> {
        try {
            const { data } = await withRetry(() => client.get(`/authors/${id}`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getAuthorEntries(
        id: string,
        limit = 50,
        offset = 0,
        sortBy = 'year',
        sortOrder = 'desc'
    ): Promise<AuthorEntryItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/authors/${id}/entries`, {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    // Venue methods
    async listVenues(limit = 100, offset = 0, sortBy = 'name', sortOrder = 'asc', category?: string): Promise<VenueListItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get('/venues', {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder, category }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getVenue(slug: string): Promise<VenueDetail> {
        try {
            const { data } = await withRetry(() => client.get(`/venues/${slug}`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getVenueEntries(slug: string, limit = 50, offset = 0, sortBy = 'year', sortOrder = 'desc'): Promise<EntityEntryItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/venues/${slug}/entries`, {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    // Subject methods
    async listSubjects(limit = 100, offset = 0, sortBy = 'name', sortOrder = 'asc'): Promise<SubjectListItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get('/subjects', {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getSubject(slug: string): Promise<SubjectDetail> {
        try {
            const { data } = await withRetry(() => client.get(`/subjects/${slug}`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getSubjectEntries(slug: string, limit = 50, offset = 0, sortBy = 'year', sortOrder = 'desc'): Promise<EntityEntryItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/subjects/${slug}/entries`, {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    // Topic methods
    async listTopics(limit = 100, offset = 0, sortBy = 'name', sortOrder = 'asc'): Promise<TopicListItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get('/topics', {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getTopic(slug: string): Promise<TopicDetail> {
        try {
            const { data } = await withRetry(() => client.get(`/topics/${slug}`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getTopicEntries(slug: string, limit = 50, offset = 0, sortBy = 'year', sortOrder = 'desc'): Promise<EntityEntryItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/topics/${slug}/entries`, {
                    params: { limit, offset, sort_by: sortBy, sort_order: sortOrder }
                })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },
}

export default api
