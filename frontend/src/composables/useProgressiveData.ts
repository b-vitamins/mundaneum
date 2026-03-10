import type { Ref } from 'vue'

import { usePollingResource, type PollingResourceOptions } from '@/composables/usePollingResource'

/**
 * Generic progressive data loading composable (Sussman-style).
 *
 * Given a fetcher function, provides reactive state for data that may
 * arrive asynchronously. Optionally polls while a predicate is true
 * (e.g., while backend is still syncing).
 *
 * Usage:
 *   const s2 = useProgressiveData(() => api.getEntryS2(id), {
 *     pollWhile: (d) => d.sync_status === 'syncing',
 *     interval: 5000,
 *   })
 *   // s2.data, s2.loading, s2.syncing, s2.ready, s2.error
 */
export type ProgressiveOptions<T> = PollingResourceOptions<T>

export interface ProgressiveState<T> {
    data: Ref<T | null>
    loading: Ref<boolean>
    syncing: Ref<boolean>
    error: Ref<string>
    ready: Ref<boolean>
    fetch: () => Promise<void>
}

export function useProgressiveData<T>(
    fetcher: () => Promise<T>,
    options: ProgressiveOptions<T> = {}
): ProgressiveState<T> {
    const resource = usePollingResource(fetcher, options)
    return {
        data: resource.data as Ref<T | null>,
        loading: resource.loading,
        syncing: resource.syncing,
        error: resource.error,
        ready: resource.ready,
        fetch: resource.fetch,
    }
}
