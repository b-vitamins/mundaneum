import { api, type EntityEntryItem } from '@/api/client'
import { groupSubjectCards } from '@/catalog/subjectGroups'
import type {
    CatalogDetailPageModel,
    CatalogEntryCard,
    CatalogListPageModel,
} from '@/catalog/types'

function subjectGroupTitle(parentSlug: string | null): string {
    if (!parentSlug) {
        return 'Other'
    }

    return parentSlug
        .split('-')
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ')
}

function buildEntryCard(entry: EntityEntryItem): CatalogEntryCard {
    const authorLabel =
        entry.authors.length > 0
            ? `${entry.authors[0]}${entry.authors.length > 1 ? ' et al.' : ''}`
            : null

    return {
        id: entry.id,
        title: entry.title,
        read: entry.read,
        badge: entry.entry_type,
        meta: [entry.entry_type, entry.year, authorLabel, entry.venue]
            .filter((value): value is string | number => Boolean(value))
            .map(String),
    }
}

export const subjectListPageModel: CatalogListPageModel = {
    title: 'Subject Areas',
    loadingLabel: 'Loading subjects...',
    emptyLabel: 'No subjects found.',
    defaultSort: { field: 'name', label: 'Name', defaultOrder: 'asc' },
    sortOptions: [],
    loadItems: () =>
        api.listSubjects(200, 0, 'name', 'asc').then(items =>
            items.map(item => ({
                id: item.slug,
                href: `/subjects/${item.slug}`,
                title: item.display_name || item.name,
                count: item.entry_count,
                countLabel: String(item.entry_count),
                groupKey: item.parent_slug,
                groupTitle: subjectGroupTitle(item.parent_slug),
            }))
        ),
    countLabel: items => `${items.length} subjects`,
    groupItems: groupSubjectCards,
}

export const subjectDetailPageModel: CatalogDetailPageModel = {
    titleFallback: 'Subject',
    backTo: '/subjects',
    backLabel: 'Subjects',
    routeParam: 'slug',
    loadingLabel: 'Loading...',
    notFoundLabel: 'Subject not found',
    sectionTitle: 'Entries',
    emptyLabel: 'No entries found.',
    loadPage: async param => {
        const [detail, entries] = await Promise.all([
            api.getSubject(param),
            api.getSubjectEntries(param),
        ])

        return {
            title: detail.name,
            statsLabel: `${detail.entry_count} entries`,
            secondaryLines: [],
            entries: entries.map(buildEntryCard),
        }
    },
}
