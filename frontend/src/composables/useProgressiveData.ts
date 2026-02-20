import { ref, onUnmounted, type Ref } from 'vue'

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
export interface ProgressiveOptions<T> {
    /** Keep polling while this returns true on fetched data */
    pollWhile?: (data: T) => boolean
    /** Poll interval in ms (default: 5000) */
    interval?: number
    /** Don't fetch on creation (call .fetch() manually) */
    lazy?: boolean
}

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
    const { pollWhile, interval = 5000, lazy = false } = options

    const data = ref<T | null>(null) as Ref<T | null>
    const loading = ref(!lazy)
    const syncing = ref(false)
    const error = ref('')
    const ready = ref(false)

    let timer: ReturnType<typeof setTimeout> | null = null
    let unmounted = false

    async function doFetch() {
        try {
            const result = await fetcher()
            if (unmounted) return

            data.value = result
            error.value = ''

            // Check if we should keep polling
            if (pollWhile && pollWhile(result)) {
                syncing.value = true
                ready.value = false
                schedulePoll()
            } else {
                syncing.value = false
                ready.value = true
            }
        } catch (e) {
            if (unmounted) return
            error.value = e instanceof Error ? e.message : 'Failed to load data'
            syncing.value = false
            ready.value = false
        } finally {
            if (!unmounted) {
                loading.value = false
            }
        }
    }

    function schedulePoll() {
        if (unmounted) return
        timer = setTimeout(() => {
            if (!unmounted) doFetch()
        }, interval)
    }

    // Auto-fetch unless lazy
    if (!lazy) {
        doFetch()
    }

    onUnmounted(() => {
        unmounted = true
        if (timer) clearTimeout(timer)
    })

    return { data, loading, syncing, error, ready, fetch: doFetch }
}
