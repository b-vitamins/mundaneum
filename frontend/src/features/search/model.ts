import type { LocationQuery } from 'vue-router'
import type { SearchFilters, SearchQueryInput, SearchSort, SearchWarning } from '@/api/types'

export type TernaryFilter = '' | 'true' | 'false'

export interface SearchFilterForm {
    entry_type: string
    year_from: number | null
    year_to: number | null
    has_pdf: TernaryFilter
    read: TernaryFilter
}

export function defaultSearchFilters(): SearchFilterForm {
    return {
        entry_type: '',
        year_from: null,
        year_to: null,
        has_pdf: '',
        read: '',
    }
}

export function parseTernaryFilter(value: TernaryFilter): boolean | undefined {
    if (value === 'true') return true
    if (value === 'false') return false
    return undefined
}

function parseRouteNumber(value: LocationQuery[string]): number | null {
    if (typeof value !== 'string' || value.trim() === '') {
        return null
    }
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
}

function parseRouteTernary(value: LocationQuery[string]): TernaryFilter {
    return value === 'true' || value === 'false' ? value : ''
}

function pickFirst(value: LocationQuery[string]): string {
    return typeof value === 'string' ? value : ''
}

export function readSearchQuery(query: LocationQuery): { query: string; filters: SearchFilterForm } {
    return {
        query: pickFirst(query.q),
        filters: {
            entry_type: pickFirst(query.entry_type),
            year_from: parseRouteNumber(query.year_from),
            year_to: parseRouteNumber(query.year_to),
            has_pdf: parseRouteTernary(query.has_pdf),
            read: parseRouteTernary(query.read),
        },
    }
}

export function buildSearchFilters(filters: SearchFilterForm): SearchFilters {
    const activeFilters: SearchFilters = {}
    if (filters.entry_type) activeFilters.entry_type = filters.entry_type
    if (filters.year_from !== null) activeFilters.year_from = filters.year_from
    if (filters.year_to !== null) activeFilters.year_to = filters.year_to

    const hasPdf = parseTernaryFilter(filters.has_pdf)
    if (hasPdf !== undefined) activeFilters.has_pdf = hasPdf

    const read = parseTernaryFilter(filters.read)
    if (read !== undefined) activeFilters.read = read

    return activeFilters
}

export function buildSearchRequest(
    query: string,
    filters: SearchFilterForm,
    sort?: SearchSort,
): SearchQueryInput {
    return {
        query,
        filters: buildSearchFilters(filters),
        sort,
    }
}

export function buildSearchRouteQuery(query: string, filters: SearchFilterForm): Record<string, string> {
    const routeQuery: Record<string, string> = {}
    const normalizedQuery = query.trim()
    if (normalizedQuery) routeQuery.q = normalizedQuery
    if (filters.entry_type) routeQuery.entry_type = filters.entry_type
    if (filters.year_from !== null) routeQuery.year_from = String(filters.year_from)
    if (filters.year_to !== null) routeQuery.year_to = String(filters.year_to)
    if (filters.has_pdf) routeQuery.has_pdf = filters.has_pdf
    if (filters.read) routeQuery.read = filters.read
    return routeQuery
}

export function primarySearchWarning(warnings: SearchWarning[]): string {
    return warnings[0]?.message ?? ''
}

export function lastSearchWarning(warnings: SearchWarning[]): string {
    return warnings[warnings.length - 1]?.message ?? ''
}
