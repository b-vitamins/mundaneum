import { ApiError } from '@/api/base'
import { adminApi } from '@/api/admin'
import { catalogApi } from '@/api/catalog'
import { collectionApi } from '@/api/collections'
import { libraryApi } from '@/api/library'
import { searchApi } from '@/api/search'

export const api = {
    ...libraryApi,
    ...searchApi,
    ...collectionApi,
    ...adminApi,
    ...catalogApi,
}

export { ApiError }
export * from '@/api/types'
