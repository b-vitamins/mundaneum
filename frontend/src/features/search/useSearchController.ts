import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
    api,
    type SearchHit,
    type SearchStatus,
    type SearchWarning,
} from '@/api/client'
import {
    buildSearchRequest,
    buildSearchRouteQuery,
    defaultSearchFilters,
    lastSearchWarning,
    primarySearchWarning,
    readSearchQuery,
    type SearchFilterForm,
} from '@/features/search/model'

export type SearchViewState =
    | 'idle'
    | 'loading'
    | 'error'
    | 'unavailable'
    | 'empty'
    | 'results'

export function useSearchController() {
    const route = useRoute()
    const router = useRouter()

    const initialSearch = readSearchQuery(route.query)
    const query = ref(initialSearch.query)
    const results = ref<SearchHit[]>([])
    const total = ref(0)
    const loading = ref(false)
    const error = ref('')
    const status = ref<SearchStatus>('ok')
    const warnings = ref<SearchWarning[]>([])
    const showFilters = ref(false)
    const filters = ref<SearchFilterForm>(initialSearch.filters)
    const entryTypes = [
        'article',
        'book',
        'inproceedings',
        'phdthesis',
        'techreport',
        'misc',
    ]

    let debounceTimer: ReturnType<typeof setTimeout> | null = null

    async function search() {
        if (!query.value.trim()) {
            results.value = []
            total.value = 0
            status.value = 'ok'
            warnings.value = []
            error.value = ''
            return
        }

        loading.value = true
        error.value = ''

        try {
            const data = await api.search(buildSearchRequest(query.value, filters.value))
            status.value = data.status
            warnings.value = data.warnings
            results.value = data.hits
            total.value = data.total
        } catch (searchError) {
            console.error('Search failed:', searchError)
            error.value = 'Search failed'
            status.value = 'unavailable'
            warnings.value = []
        } finally {
            loading.value = false
        }
    }

    function syncRoute() {
        router.replace({ query: buildSearchRouteQuery(query.value, filters.value) })
    }

    function debouncedSearch() {
        if (debounceTimer) {
            clearTimeout(debounceTimer)
        }

        debounceTimer = setTimeout(() => {
            syncRoute()
            void search()
        }, 300)
    }

    function handleSearch() {
        syncRoute()
        void search()
    }

    function applyFilters() {
        syncRoute()
        void search()
    }

    function clearFilters() {
        filters.value = defaultSearchFilters()
        syncRoute()
        void search()
    }

    watch(
        () => route.query,
        newQuery => {
            const nextSearch = readSearchQuery(newQuery)
            query.value = nextSearch.query
            filters.value = nextSearch.filters
            void search()
        },
        { immediate: true }
    )

    watch(query, () => {
        debouncedSearch()
    })

    onUnmounted(() => {
        if (debounceTimer) {
            clearTimeout(debounceTimer)
        }
    })

    const partialWarning = computed(() => primarySearchWarning(warnings.value))
    const unavailableDetail = computed(() => lastSearchWarning(warnings.value))
    const viewState = computed<SearchViewState>(() => {
        if (loading.value) return 'loading'
        if (error.value) return 'error'
        if (status.value === 'unavailable') return 'unavailable'
        if (!query.value.trim()) return 'idle'
        if (results.value.length === 0) return 'empty'
        return 'results'
    })

    return {
        applyFilters,
        clearFilters,
        entryTypes,
        error,
        filters,
        handleSearch,
        loading,
        partialWarning,
        query,
        results,
        showFilters,
        status,
        total,
        unavailableDetail,
        viewState,
    }
}
