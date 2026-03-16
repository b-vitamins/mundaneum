import { client, handleError, withRetry } from '@/api/base'

export interface BundleListItem {
    bundle_index: number
    bundle_id?: string | null
    lifecycle?: string | null
    size: number
    venue_count: number
    venue_coverage: string[]
    top_entities: Array<{
        canonical_id?: string | null
        canonical_surface: string
        label: string
        node_key?: string | null
        paper_hits: number
    }>
    growth_indicator: 'growing' | 'declining' | 'stable'
}

export interface BundleDetail {
    bundle_index: number
    bundle_id?: string | null
    lifecycle?: string | null
    birth_year?: number | null
    latest_year?: number | null
    size: number
    latest_year_papers: number
    venue_count: number
    growth_rate: number
    cohesion: number
    internal_edge_weight: number
    external_edge_weight: number
    venue_coverage: string[]
    members: string[]
    top_entities: Array<{
        canonical_id?: string | null
        canonical_surface: string
        label: string
        node_key?: string | null
        paper_hits: number
    }>
    yearly_paper_counts: Record<string, number>
    previous_year_papers: number
}

export interface EntityNeighbor {
    canonical_id: string
    canonical_surface: string
    label: string
    paper_count: number
}

export interface CooccurrenceEdgeItem {
    left_node: string
    left_canonical_id?: string | null
    left_label: string
    right_node: string
    right_canonical_id?: string | null
    right_label: string
    paper_count: number
    venue: string
    year: number
}

export const conceptsApi = {
    async listBundles(limit = 100, offset = 0): Promise<BundleListItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get('/concepts/bundles', { params: { limit, offset } })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getBundle(bundleIndex: number): Promise<BundleDetail> {
        try {
            const { data } = await withRetry(() => client.get(`/concepts/bundles/${bundleIndex}`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getEntityNeighbors(canonicalId: string, params: {
        limit?: number; venue?: string; year?: number;
    } = {}): Promise<EntityNeighbor[]> {
        try {
            const { data } = await withRetry(() =>
                client.get(`/concepts/neighbors/${canonicalId}`, { params })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getCooccurrenceEdges(params: {
        canonical_id?: string; venue?: string; year?: number;
        min_paper_count?: number; limit?: number; offset?: number;
    } = {}): Promise<CooccurrenceEdgeItem[]> {
        try {
            const { data } = await withRetry(() =>
                client.get('/concepts/edges', { params })
            )
            return data
        } catch (error) {
            return handleError(error)
        }
    },
}
