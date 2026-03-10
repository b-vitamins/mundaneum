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

export const topicListPageModel: CatalogListPageModel = {
    title: 'Topics',
    loadingLabel: 'Loading topics...',
    emptyLabel: 'No topics found.',
    defaultSort: { field: 'name', label: 'Name', defaultOrder: 'asc' },
    sortOptions: [
        { field: 'name', label: 'Name', defaultOrder: 'asc' },
        { field: 'entry_count', label: 'Entry Count', defaultOrder: 'desc' },
    ],
    loadItems: ({ sortBy, sortOrder }) =>
        api.listTopics(200, 0, sortBy, sortOrder).then(items =>
            items.map(item => ({
                id: item.slug,
                href: `/topics/${item.slug}`,
                title: item.name,
                count: item.entry_count,
                countLabel: String(item.entry_count),
            }))
        ),
    countLabel: items => `${items.length} topics`,
}

export const topicDetailPageModel: CatalogDetailPageModel = {
    titleFallback: 'Topic',
    backTo: '/topics',
    backLabel: 'Topics',
    routeParam: 'slug',
    loadingLabel: 'Loading...',
    notFoundLabel: 'Topic not found',
    sectionTitle: 'Entries',
    emptyLabel: 'No entries found.',
    loadPage: async param => {
        const [detail, entries] = await Promise.all([
            api.getTopic(param),
            api.getTopicEntries(param),
        ])

        return {
            title: detail.name,
            statsLabel: `${detail.entry_count} entries`,
            secondaryLines: [],
            entries: entries.map(buildEntryCard),
        }
    },
}
