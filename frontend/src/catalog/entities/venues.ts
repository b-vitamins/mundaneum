import { api, type EntityEntryItem } from '@/api/client'
import type {
    CatalogDetailPageModel,
    CatalogEntryCard,
    CatalogListPageModel,
} from '@/catalog/types'

function buildEntryMeta(entry: EntityEntryItem): string[] {
    const authorLabel =
        entry.authors.length > 0
            ? `${entry.authors[0]}${entry.authors.length > 1 ? ' et al.' : ''}`
            : null

    return [entry.entry_type, entry.year, authorLabel, entry.venue]
        .filter((value): value is string | number => Boolean(value))
        .map(String)
}

function buildEntryCard(entry: EntityEntryItem): CatalogEntryCard {
    return {
        id: entry.id,
        title: entry.title,
        read: entry.read,
        badge: entry.entry_type,
        meta: buildEntryMeta(entry),
    }
}

export const venueListPageModel: CatalogListPageModel = {
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
        api.listVenues(200, 0, sortBy, sortOrder, category).then(items =>
            items.map(item => ({
                id: item.slug,
                href: `/venues/${item.slug}`,
                title: item.name,
                count: item.entry_count,
                countLabel: String(item.entry_count),
                badge: item.category,
            }))
        ),
    countLabel: items => `${items.length} venues`,
}

export const venueDetailPageModel: CatalogDetailPageModel = {
    titleFallback: 'Venue',
    backTo: '/venues',
    backLabel: 'Venues',
    routeParam: 'slug',
    loadingLabel: 'Loading...',
    notFoundLabel: 'Venue not found',
    sectionTitle: 'Publications',
    emptyLabel: 'No entries found.',
    loadPage: async param => {
        const [detail, entries] = await Promise.all([
            api.getVenue(param),
            api.getVenueEntries(param),
        ])

        return {
            title: detail.name,
            statsLabel: `${detail.entry_count} publications`,
            badge: detail.category,
            secondaryLines:
                detail.aliases.length > 0
                    ? [`Also known as: ${detail.aliases.join(', ')}`]
                    : [],
            entries: entries.map(buildEntryCard),
        }
    },
}
