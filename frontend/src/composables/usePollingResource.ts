import { onUnmounted, ref, type Ref } from 'vue'

export interface PollingResourceOptions<T> {
    pollWhile?: (data: T) => boolean
    interval?: number
    lazy?: boolean
}

export interface PollingResourceState<T> {
    data: Ref<T | null>
    loading: Ref<boolean>
    syncing: Ref<boolean>
    error: Ref<string>
    ready: Ref<boolean>
    fetch: () => Promise<void>
    reset: () => void
    stop: () => void
}

export function usePollingResource<T>(
    fetcher: () => Promise<T>,
    options: PollingResourceOptions<T> = {}
): PollingResourceState<T> {
    const { pollWhile, interval = 5000, lazy = false } = options

    const data = ref<T | null>(null) as Ref<T | null>
    const loading = ref(!lazy)
    const syncing = ref(false)
    const error = ref('')
    const ready = ref(false)

    let timer: ReturnType<typeof setTimeout> | null = null
    let requestVersion = 0
    let disposed = false
    let loadedOnce = false

    function clearTimer() {
        if (timer) {
            clearTimeout(timer)
            timer = null
        }
    }

    function stop() {
        disposed = true
        requestVersion += 1
        clearTimer()
    }

    function reset() {
        requestVersion += 1
        clearTimer()
        data.value = null
        loading.value = !lazy
        syncing.value = false
        error.value = ''
        ready.value = false
        loadedOnce = false
    }

    function schedulePoll() {
        clearTimer()
        if (disposed) {
            return
        }
        timer = setTimeout(() => {
            if (!disposed) {
                void fetch()
            }
        }, interval)
    }

    async function fetch() {
        const version = ++requestVersion
        clearTimer()

        if (!loadedOnce) {
            loading.value = true
        }

        try {
            const result = await fetcher()
            if (disposed || version !== requestVersion) {
                return
            }

            data.value = result
            error.value = ''
            loadedOnce = true

            if (pollWhile && pollWhile(result)) {
                syncing.value = true
                ready.value = false
                schedulePoll()
            } else {
                syncing.value = false
                ready.value = true
            }
        } catch (loadError) {
            if (disposed || version !== requestVersion) {
                return
            }
            error.value = loadError instanceof Error ? loadError.message : 'Failed to load data'
            syncing.value = false
            ready.value = false
        } finally {
            if (!disposed && version === requestVersion) {
                loading.value = false
            }
        }
    }

    if (!lazy) {
        void fetch()
    }

    onUnmounted(stop)

    return { data, loading, syncing, error, ready, fetch, reset, stop }
}
