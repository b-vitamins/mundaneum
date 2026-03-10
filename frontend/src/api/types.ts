import type { components } from '@/api/generated'

type Schema<Name extends keyof components['schemas']> = components['schemas'][Name]

export type Stats = Schema<'StatsResponse'>

export type EntryListItem = Schema<'EntryResponse'>
export type SearchHit = Schema<'SearchHitResponse'>
export type SearchStatus = Schema<'SearchStatus'>
export type SearchSource = Schema<'SearchSource'>
export type SearchWarningCode = Schema<'SearchWarningCode'>
export type SearchWarning = Schema<'SearchWarning'>
export type SearchResponse = Omit<Schema<'SearchResponse'>, 'warnings'> & {
    warnings: SearchWarning[]
}
export type EntryDetail = Schema<'EntryDetailResponse'>
export type S2Meta = Schema<'S2MetaResponse'>
export type S2Paper = Schema<'S2PaperResponse'>
export type GraphNode = Omit<Schema<'GraphNodeResponse'>, 'year'> & {
    year: number | null
}
export type GraphEdge = Schema<'GraphEdgeResponse'>
export type SimilarityEdge = Schema<'SimilarityEdgeResponse'>
export type AggregateEntry = Schema<'AggregateEntryResponse'>
export interface GraphData {
    center_id: string
    nodes: GraphNode[]
    edges: GraphEdge[]
    similarity_edges: SimilarityEdge[]
    prior_works: AggregateEntry[]
    derivative_works: AggregateEntry[]
}
export type Collection = Schema<'CollectionResponse'>
export type CollectionDetail = Schema<'CollectionDetailResponse'>
export type AdminHealth = Schema<'HealthResponse'>
export type ExportedEntry = Schema<'ExportedEntry'>
export type ExportedCollection = Schema<'ExportedCollection'>
export type ExportData = Schema<'ExportData'>
export type ImportResult = Schema<'ImportResult'>
export type AuthorListItem = Schema<'AuthorListItem'>
export type AuthorDetail = Schema<'AuthorDetail'>
export type AuthorEntryItem = Schema<'AuthorEntryItem'>
export type VenueListItem = Schema<'VenueListItem'>
export type VenueDetail = Schema<'VenueDetail'>
export type SubjectListItem = Omit<Schema<'SubjectListItem'>, 'parent_slug' | 'display_name'> & {
    parent_slug: string | null
    display_name: string | null
}
export type SubjectDetail = Schema<'SubjectDetail'>
export type TopicListItem = Schema<'TopicListItem'>
export type TopicDetail = Schema<'TopicDetail'>
export type SubjectEntryItem = Schema<'SubjectEntryItem'>
export type TopicEntryItem = Schema<'TopicEntryItem'>
export type VenueEntryItem = Schema<'VenueEntryItem'>
export type EntityEntryItem = (SubjectEntryItem | TopicEntryItem | VenueEntryItem) & {
    venue?: string | null
}

export type SearchSortField = 'created_at' | 'year' | 'title'
export type SearchSortOrder = 'asc' | 'desc'

export interface SearchSort {
    field: SearchSortField
    order: SearchSortOrder
}

export interface SearchFilters {
    entry_type?: string
    year_from?: number
    year_to?: number
    has_pdf?: boolean
    read?: boolean
}

export interface SearchQueryInput {
    query: string
    filters?: SearchFilters
    limit?: number
    offset?: number
    sort?: SearchSort
}
