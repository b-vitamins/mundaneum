import { computed, onUnmounted, ref, watch, type Ref } from 'vue'

export interface RouteResourceState<T> {
    data: Ref<T | null>
    loading: Ref<boolean>
    error: Ref<string>
    ready: Ref<boolean>
    reload: () => Promise<void>
}

export interface RouteResourceOptions<TKey, TData> {
    key: () => TKey | null | undefined
    fetcher: (key: TKey) => Promise<TData>
    immediate?: boolean
    clearOnReload?: boolean
}

export function useRouteResource<TKey, TData>(
    options: RouteResourceOptions<TKey, TData>
): RouteResourceState<TData> {
    const { fetcher, immediate = true, clearOnReload = true } = options

    const data = ref<TData | null>(null) as Ref<TData | null>
    const loading = ref(false)
    const error = ref('')
    const ready = ref(false)

    const key = computed(() => options.key())
    let requestVersion = 0
    let disposed = false

    async function reload() {
        const currentKey = key.value
        if (currentKey == null || currentKey === '') {
            data.value = null
            loading.value = false
            ready.value = false
            error.value = ''
            return
        }

        const version = ++requestVersion
        loading.value = true
        error.value = ''
        ready.value = false
        if (clearOnReload) {
            data.value = null
        }

        try {
            const result = await fetcher(currentKey)
            if (disposed || version !== requestVersion) {
                return
            }
            data.value = result
            ready.value = true
        } catch (loadError) {
            if (disposed || version !== requestVersion) {
                return
            }
            error.value = loadError instanceof Error ? loadError.message : 'Failed to load resource'
        } finally {
            if (!disposed && version === requestVersion) {
                loading.value = false
            }
        }
    }

    watch(key, () => {
        if (immediate) {
            void reload()
        }
    }, { immediate })

    onUnmounted(() => {
        disposed = true
        requestVersion += 1
    })

    return { data, loading, error, ready, reload }
}
