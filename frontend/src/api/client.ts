import { ApiError } from '@/api/base'
import { adminApi } from '@/api/admin'
import { catalogApi } from '@/api/catalog'
import { collectionApi } from '@/api/collections'
import { conceptsApi } from '@/api/concepts'
import { libraryApi } from '@/api/library'
import { nerApi } from '@/api/ner'
import { searchApi } from '@/api/search'
import { trendsApi } from '@/api/trends'

export const api = {
    ...libraryApi,
    ...searchApi,
    ...collectionApi,
    ...adminApi,
    ...catalogApi,
    ...nerApi,
    ...trendsApi,
    ...conceptsApi,
}

export { ApiError }
export * from '@/api/types'
export * from '@/api/ner'
export * from '@/api/trends'
export * from '@/api/concepts'
