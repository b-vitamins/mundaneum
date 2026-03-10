import { api } from '@/api/client'
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
} from '@/api/client'

export type CatalogEntityKey = 'authors' | 'venues' | 'subjects' | 'topics'
export type CatalogSortField = 'name' | 'entry_count'
export type CatalogSortOrder = 'asc' | 'desc'

export type CatalogListItem =
    | AuthorListItem
    | VenueListItem
    | SubjectListItem
    | TopicListItem

export type CatalogDetailItem =
    | AuthorDetail
    | VenueDetail
    | SubjectDetail
    | TopicDetail

export type CatalogEntryItem = AuthorEntryItem | EntityEntryItem

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

export interface SubjectGroup {
    title: string
    icon: string
    entryCount: number
    items: SubjectListItem[]
}

export interface CatalogListPageModel {
    title: string
    loadingLabel: string
    emptyLabel: string
    defaultSort: CatalogSortOption
    sortOptions: CatalogSortOption[]
    loadItems: (state: CatalogListState) => Promise<CatalogListItem[]>
    countLabel: (items: CatalogListItem[]) => string
    itemHref: (item: CatalogListItem) => string
    itemTitle: (item: CatalogListItem) => string
    itemCountLabel: (item: CatalogListItem) => string
    itemBadge?: (item: CatalogListItem) => string | null
    groupItems?: (items: CatalogListItem[]) => SubjectGroup[]
    categoryOptions?: CatalogFilterOption[]
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
    loadDetail: (param: string) => Promise<CatalogDetailItem>
    loadEntries: (param: string) => Promise<CatalogEntryItem[]>
    title: (detail: CatalogDetailItem) => string
    statsLabel: (detail: CatalogDetailItem) => string
    badge?: (detail: CatalogDetailItem) => string | null
    secondaryLines?: (detail: CatalogDetailItem) => string[]
    entryMeta: (entry: CatalogEntryItem) => string[]
}

const subjectIcons: Record<string, string> = {
    Physics: '⚛️',
    'Computer Science': '💻',
    Mathematics: '📐',
    Programming: '🖥️',
    Statistics: '📊',
    Biology: '🧬',
    Chemistry: '🧪',
    Economics: '📈',
    Engineering: '⚙️',
    Neuroscience: '🧠',
    Philosophy: '🤔',
    Design: '🎨',
    Environment: '🌱',
    Other: '📚',
}

function subjectGroupTitle(parentSlug: string | null): string {
    if (!parentSlug) {
        return 'Other'
    }
    return parentSlug
        .split('-')
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ')
}

function asAuthorListItem(item: CatalogListItem): AuthorListItem {
    return item as AuthorListItem
}

function asVenueListItem(item: CatalogListItem): VenueListItem {
    return item as VenueListItem
}

function asSubjectListItem(item: CatalogListItem): SubjectListItem {
    return item as SubjectListItem
}

function asTopicListItem(item: CatalogListItem): TopicListItem {
    return item as TopicListItem
}

function asAuthorDetail(detail: CatalogDetailItem): AuthorDetail {
    return detail as AuthorDetail
}

function asVenueDetail(detail: CatalogDetailItem): VenueDetail {
    return detail as VenueDetail
}

function asSubjectDetail(detail: CatalogDetailItem): SubjectDetail {
    return detail as SubjectDetail
}

function asTopicDetail(detail: CatalogDetailItem): TopicDetail {
    return detail as TopicDetail
}

function authorEntryMeta(entry: CatalogEntryItem): string[] {
    const authorEntry = entry as AuthorEntryItem
    return [authorEntry.entry_type, authorEntry.year, authorEntry.venue]
        .filter((value): value is string | number => Boolean(value))
        .map(String)
}

function entityEntryMeta(entry: CatalogEntryItem): string[] {
    const entityEntry = entry as EntityEntryItem
    const authorLabel =
        entityEntry.authors.length > 0
            ? `${entityEntry.authors[0]}${entityEntry.authors.length > 1 ? ' et al.' : ''}`
            : null
    return [entityEntry.entry_type, entityEntry.year, authorLabel, entityEntry.venue]
        .filter((value): value is string | number => Boolean(value))
        .map(String)
}

function groupSubjects(items: CatalogListItem[]): SubjectGroup[] {
    const groups = new Map<string, SubjectListItem[]>()
    for (const item of items) {
        const subject = asSubjectListItem(item)
        const title = subjectGroupTitle(subject.parent_slug)
        const existing = groups.get(title) ?? []
        existing.push(subject)
        groups.set(title, existing)
    }

    return Array.from(groups.entries())
        .sort(([left], [right]) => {
            if (left === 'Other') return 1
            if (right === 'Other') return -1
            return left.localeCompare(right)
        })
        .map(([title, groupItems]) => ({
            title,
            icon: subjectIcons[title] ?? '📁',
            entryCount: groupItems.reduce((sum, subject) => sum + subject.entry_count, 0),
            items: [...groupItems].sort((left, right) => right.entry_count - left.entry_count),
        }))
}

export const catalogListPageModels: Record<CatalogEntityKey, CatalogListPageModel> = {
    authors: {
        title: 'Authors',
        loadingLabel: 'Loading authors...',
        emptyLabel: 'No authors found.',
        defaultSort: { field: 'name', label: 'Name', defaultOrder: 'asc' },
        sortOptions: [
            { field: 'name', label: 'Name', defaultOrder: 'asc' },
            { field: 'entry_count', label: 'Entry Count', defaultOrder: 'desc' },
        ],
        loadItems: ({ sortBy, sortOrder }) => api.listAuthors(200, 0, sortBy, sortOrder),
        countLabel: items => `${items.length} authors`,
        itemHref: item => `/authors/${asAuthorListItem(item).id}`,
        itemTitle: item => asAuthorListItem(item).name,
        itemCountLabel: item => String(asAuthorListItem(item).entry_count),
    },
    venues: {
        title: 'Venues',
        loadingLabel: 'Loading venues...',
        emptyLabel: 'No venues found.',
        defaultSort: { field: 'name', label: 'Name', defaultOrder: 'asc' },
        sortOptions: [
            { field: 'name', label: 'Name', defaultOrder: 'asc' },
            { field: 'entry_count', label: 'Entry Count', defaultOrder: 'desc' },
        ],
        categoryOptions: [
            { label: 'All' },
            { value: 'CONFERENCE', label: 'Conferences' },
            { value: 'JOURNAL', label: 'Journals' },
        ],
        loadItems: ({ sortBy, sortOrder, category }) =>
            api.listVenues(200, 0, sortBy, sortOrder, category),
        countLabel: items => `${items.length} venues`,
        itemHref: item => `/venues/${asVenueListItem(item).slug}`,
        itemTitle: item => asVenueListItem(item).name,
        itemCountLabel: item => String(asVenueListItem(item).entry_count),
        itemBadge: item => asVenueListItem(item).category,
    },
    subjects: {
        title: 'Subject Areas',
        loadingLabel: 'Loading subjects...',
        emptyLabel: 'No subjects found.',
        defaultSort: { field: 'name', label: 'Name', defaultOrder: 'asc' },
        sortOptions: [],
        loadItems: () => api.listSubjects(200, 0, 'name', 'asc'),
        countLabel: items => `${items.length} subjects`,
        itemHref: item => `/subjects/${asSubjectListItem(item).slug}`,
        itemTitle: item => asSubjectListItem(item).display_name || asSubjectListItem(item).name,
        itemCountLabel: item => String(asSubjectListItem(item).entry_count),
        groupItems: groupSubjects,
    },
    topics: {
        title: 'Topics',
        loadingLabel: 'Loading topics...',
        emptyLabel: 'No topics found.',
        defaultSort: { field: 'name', label: 'Name', defaultOrder: 'asc' },
        sortOptions: [
            { field: 'name', label: 'Name', defaultOrder: 'asc' },
            { field: 'entry_count', label: 'Entry Count', defaultOrder: 'desc' },
        ],
        loadItems: ({ sortBy, sortOrder }) => api.listTopics(200, 0, sortBy, sortOrder),
        countLabel: items => `${items.length} topics`,
        itemHref: item => `/topics/${asTopicListItem(item).slug}`,
        itemTitle: item => asTopicListItem(item).name,
        itemCountLabel: item => String(asTopicListItem(item).entry_count),
    },
}

export const catalogDetailPageModels: Record<CatalogEntityKey, CatalogDetailPageModel> = {
    authors: {
        titleFallback: 'Author',
        backTo: '/authors',
        backLabel: 'Authors',
        routeParam: 'id',
        loadingLabel: 'Loading...',
        notFoundLabel: 'Author not found',
        sectionTitle: 'Publications',
        emptyLabel: 'No entries found for this author.',
        loadDetail: param => api.getAuthor(param),
        loadEntries: param => api.getAuthorEntries(param),
        title: detail => asAuthorDetail(detail).name,
        statsLabel: detail => `${asAuthorDetail(detail).entry_count} publications`,
        entryMeta: authorEntryMeta,
    },
    venues: {
        titleFallback: 'Venue',
        backTo: '/venues',
        backLabel: 'Venues',
        routeParam: 'slug',
        loadingLabel: 'Loading...',
        notFoundLabel: 'Venue not found',
        sectionTitle: 'Publications',
        emptyLabel: 'No entries found.',
        loadDetail: param => api.getVenue(param),
        loadEntries: param => api.getVenueEntries(param),
        title: detail => asVenueDetail(detail).name,
        statsLabel: detail => `${asVenueDetail(detail).entry_count} publications`,
        badge: detail => asVenueDetail(detail).category,
        secondaryLines: detail => {
            const venue = asVenueDetail(detail)
            return venue.aliases.length > 0
                ? [`Also known as: ${venue.aliases.join(', ')}`]
                : []
        },
        entryMeta: entityEntryMeta,
    },
    subjects: {
        titleFallback: 'Subject',
        backTo: '/subjects',
        backLabel: 'Subjects',
        routeParam: 'slug',
        loadingLabel: 'Loading...',
        notFoundLabel: 'Subject not found',
        sectionTitle: 'Entries',
        emptyLabel: 'No entries found.',
        loadDetail: param => api.getSubject(param),
        loadEntries: param => api.getSubjectEntries(param),
        title: detail => asSubjectDetail(detail).name,
        statsLabel: detail => `${asSubjectDetail(detail).entry_count} entries`,
        entryMeta: entityEntryMeta,
    },
    topics: {
        titleFallback: 'Topic',
        backTo: '/topics',
        backLabel: 'Topics',
        routeParam: 'slug',
        loadingLabel: 'Loading...',
        notFoundLabel: 'Topic not found',
        sectionTitle: 'Entries',
        emptyLabel: 'No entries found.',
        loadDetail: param => api.getTopic(param),
        loadEntries: param => api.getTopicEntries(param),
        title: detail => asTopicDetail(detail).name,
        statsLabel: detail => `${asTopicDetail(detail).entry_count} entries`,
        entryMeta: entityEntryMeta,
    },
}
