import { authorDetailPageModel, authorListPageModel } from '@/catalog/entities/authors'
import { subjectDetailPageModel, subjectListPageModel } from '@/catalog/entities/subjects'
import { topicDetailPageModel, topicListPageModel } from '@/catalog/entities/topics'
import { venueDetailPageModel, venueListPageModel } from '@/catalog/entities/venues'
import type {
    CatalogDetailPageModel,
    CatalogEntityKey,
    CatalogListPageModel,
} from '@/catalog/types'

export type {
    CatalogDetailPageData,
    CatalogDetailPageModel,
    CatalogEntityKey,
    CatalogEntryCard,
    CatalogFilterOption,
    CatalogListCard,
    CatalogListPageModel,
    CatalogListState,
    CatalogSortField,
    CatalogSortOption,
    CatalogSortOrder,
    SubjectGroup,
} from '@/catalog/types'

export const catalogListPageModels: Record<CatalogEntityKey, CatalogListPageModel> = {
    authors: authorListPageModel,
    venues: venueListPageModel,
    subjects: subjectListPageModel,
    topics: topicListPageModel,
}

export const catalogDetailPageModels: Record<CatalogEntityKey, CatalogDetailPageModel> = {
    authors: authorDetailPageModel,
    venues: venueDetailPageModel,
    subjects: subjectDetailPageModel,
    topics: topicDetailPageModel,
}
