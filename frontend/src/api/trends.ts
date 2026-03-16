import { client, handleError, withRetry } from '@/api/base'

export interface TrendMoverItem {
    canonical_id: string
    canonical_surface: string
    label: string
    venue: string
    year: number
    prevalence: number
    momentum: number
    paper_hits: number
    change_point: boolean
    change_direction: 'rising' | 'falling' | 'stable'
    prevalence_z: number
}

export interface EmergenceItem {
    canonical_id: string
    canonical_surface: string
    label: string
    venue: string
    year: number
    emergence_score: number
    momentum: number
    prevalence: number
    paper_hits: number
}

export interface CrossVenueFlowItem {
    canonical_id: string
    canonical_surface: string
    label: string
    source_venue: string
    source_year: number
    target_venue: string
    target_year: number
    lag_years: number
    transfer_score: number
}

export interface TrendsDashboardStats {
    total_entities: number
    total_trend_rows: number
    emerging_count: number
    venues: string[]
    labels: string[]
    year_range: number[]
}

export interface TrendSparkline {
    canonical_id: string
    canonical_surface: string
    label: string
    points: Array<{ year: number; venue: string; prevalence: number; momentum: number; paper_hits: number }>
}

export const trendsApi = {
    async getTrendsStats(): Promise<TrendsDashboardStats> {
        try {
            const { data } = await withRetry(() => client.get('/trends/stats'))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getMovers(params: {
        limit?: number; offset?: number; sort_by?: string; sort_order?: string;
        label?: string; venue?: string; year?: number; direction?: string;
    } = {}): Promise<TrendMoverItem[]> {
        try {
            const { data } = await withRetry(() => client.get('/trends/movers', { params }))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getSparkline(canonicalId: string): Promise<TrendSparkline> {
        try {
            const { data } = await withRetry(() => client.get(`/trends/sparkline/${canonicalId}`))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getEmergence(params: {
        limit?: number; offset?: number; label?: string; venue?: string;
    } = {}): Promise<EmergenceItem[]> {
        try {
            const { data } = await withRetry(() => client.get('/trends/emergence', { params }))
            return data
        } catch (error) {
            return handleError(error)
        }
    },

    async getCrossVenueFlow(params: {
        limit?: number; offset?: number; label?: string;
        source_venue?: string; target_venue?: string; min_transfer_score?: number;
    } = {}): Promise<CrossVenueFlowItem[]> {
        try {
            const { data } = await withRetry(() => client.get('/trends/flow', { params }))
            return data
        } catch (error) {
            return handleError(error)
        }
    },
}
