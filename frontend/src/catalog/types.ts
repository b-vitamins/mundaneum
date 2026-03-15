export type CatalogEntityKey = 'authors' | 'venues' | 'subjects' | 'topics'
export type CatalogSortField = 'name' | 'entry_count'
export type CatalogSortOrder = 'asc' | 'desc'

export interface CatalogListState {
    sortBy: CatalogSortField
    sortOrder: CatalogSortOrder
    category?: string
}

export interface CatalogSortOption {
    field: CatalogSortField
    label: string
    defaultOrder: CatalogSortOrder
}

export interface CatalogFilterOption {
    value?: string
    label: string
}

export interface CatalogListCard {
    id: string
    href: string
    title: string
    count: number
    countLabel: string
    badge?: string | null
    groupKey?: string | null
    groupTitle?: string
}

export interface CatalogEntryCard {
    id: string
    title: string
    read: boolean
    badge?: string | null
    meta: string[]
}

export interface CatalogDetailPageData {
    title: string
    statsLabel: string
    badge?: string | null
    secondaryLines: string[]
    entries: CatalogEntryCard[]
}

export interface SubjectGroup {
    title: string
    icon: string
    entryCount: number
    items: CatalogListCard[]
}

export interface CatalogListPageModel {
    title: string
    loadingLabel: string
    emptyLabel: string
    helperText?: string
    defaultSort: CatalogSortOption
    sortOptions: CatalogSortOption[]
    categoryOptions?: CatalogFilterOption[]
    loadItems: (state: CatalogListState) => Promise<CatalogListCard[]>
    countLabel: (items: CatalogListCard[]) => string
    groupItems?: (items: CatalogListCard[]) => SubjectGroup[]
}

export interface CatalogDetailPageModel {
    titleFallback: string
    backTo: string
    backLabel: string
    routeParam: 'id' | 'slug'
    loadingLabel: string
    notFoundLabel: string
    sectionTitle: string
    emptyLabel: string
    loadPage: (param: string) => Promise<CatalogDetailPageData>
}
