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
    venue: string | null
    abstract: string | null
    has_pdf: boolean
    read: boolean
}

export interface SearchResponse {
    hits: SearchHit[]
    total: number
    processing_time_ms: number
}

export interface EntryDetail extends EntryListItem {
    required_fields: Record<string, unknown>
    optional_fields: Record<string, unknown>
    notes: string | null
    source_file: string
}

export interface S2Meta {
    sync_status: 'syncing' | 'synced' | 'no_match' | 'pending'
    s2_id: string | null
    title: string | null
    abstract: string | null
    tldr: string | null
    citation_count: number | null
    reference_count: number | null
    influential_citation_count: number | null
    fields_of_study: string[]
    publication_types: string[]
    is_open_access: boolean
    open_access_pdf_url: string | null
    external_ids: Record<string, unknown>
    s2_url: string | null
}

export interface SearchFilters {
    entry_type?: string
    year_from?: number
    year_to?: number
    has_pdf?: boolean
    read?: boolean
}

export interface S2Paper {
    s2_id: string
    title: string
    year?: number
    venue?: string
    authors: { authorId?: string; name: string }[]
    abstract?: string | null
    tldr?: { model?: string; text: string } | null
    citation_count: number
    is_influential: boolean
    contexts: string[]
    intents: string[]
}

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

export interface SimilarityEdge {
    source: string
    target: string
    weight: number
}

export interface AggregateEntry {
    id: string
    title: string
    year: number | null
    venue: string | null
    authors: string[]
    citation_count: number
    frequency: number
    in_library: boolean
    entry_id: string | null
}

export interface GraphData {
    center_id: string
    nodes: GraphNode[]
    edges: GraphEdge[]
    similarity_edges: SimilarityEdge[]
    prior_works: AggregateEntry[]
    derivative_works: AggregateEntry[]
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

export interface AuthorListItem {
    id: string
    name: string
    entry_count: number
}

export interface AuthorDetail extends AuthorListItem {}

export interface AuthorEntryItem {
    id: string
    citation_key: string
    entry_type: string
    title: string
    year: number | null
    venue: string | null
    read: boolean
}

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

export interface SubjectDetail extends SubjectListItem {}

export interface TopicListItem {
    id: string
    slug: string
    name: string
    entry_count: number
}

export interface TopicDetail extends TopicListItem {}
