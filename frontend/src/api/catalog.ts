import { client, handleError, withRetry } from '@/api/base'
import type {
    AuthorDetail,
    AuthorEntryItem,
    AuthorListItem,
    EntityEntryItem,
    SubjectDetail,
    SubjectListItem,
    TopicDetail,
    TopicListItem,
    VenueDetail,
    VenueListItem,
} from '@/api/types'

export const catalogApi = {
    async listAuthors(limit = 100, offset = 0, sortBy = 'name', sortOrder = 'asc'): Promise<AuthorListItem[]> {
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

    async getAuthorEntries(id: string, limit = 50, offset = 0, sortBy = 'year', sortOrder = 'desc'): Promise<AuthorEntryItem[]> {
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
