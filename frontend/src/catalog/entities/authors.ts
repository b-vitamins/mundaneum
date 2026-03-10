import { api, type AuthorEntryItem } from '@/api/client'
import type {
    CatalogDetailPageModel,
    CatalogEntryCard,
    CatalogListPageModel,
} from '@/catalog/types'

function buildEntryMeta(entry: AuthorEntryItem): string[] {
    return [entry.entry_type, entry.year, entry.venue]
        .filter((value): value is string | number => Boolean(value))
        .map(String)
}

function buildEntryCard(entry: AuthorEntryItem): CatalogEntryCard {
    return {
        id: entry.id,
        title: entry.title,
        read: entry.read,
        badge: entry.entry_type,
        meta: buildEntryMeta(entry),
    }
}

export const authorListPageModel: CatalogListPageModel = {
    title: 'Authors',
    loadingLabel: 'Loading authors...',
    emptyLabel: 'No authors found.',
    defaultSort: { field: 'name', label: 'Name', defaultOrder: 'asc' },
    sortOptions: [
        { field: 'name', label: 'Name', defaultOrder: 'asc' },
        { field: 'entry_count', label: 'Entry Count', defaultOrder: 'desc' },
    ],
    loadItems: ({ sortBy, sortOrder }) =>
        api.listAuthors(200, 0, sortBy, sortOrder).then(items =>
            items.map(item => ({
                id: item.id,
                href: `/authors/${item.id}`,
                title: item.name,
                count: item.entry_count,
                countLabel: String(item.entry_count),
            }))
        ),
    countLabel: items => `${items.length} authors`,
}

export const authorDetailPageModel: CatalogDetailPageModel = {
    titleFallback: 'Author',
    backTo: '/authors',
    backLabel: 'Authors',
    routeParam: 'id',
    loadingLabel: 'Loading...',
    notFoundLabel: 'Author not found',
    sectionTitle: 'Publications',
    emptyLabel: 'No entries found for this author.',
    loadPage: async param => {
        const [detail, entries] = await Promise.all([
            api.getAuthor(param),
            api.getAuthorEntries(param),
        ])

        return {
            title: detail.name,
            statsLabel: `${detail.entry_count} publications`,
            secondaryLines: [],
            entries: entries.map(buildEntryCard),
        }
    },
}
