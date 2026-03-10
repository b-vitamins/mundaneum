import { client, handleError, withRetry } from '@/api/base'
import type { Collection, CollectionDetail } from '@/api/types'

export const collectionApi = {
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
}
