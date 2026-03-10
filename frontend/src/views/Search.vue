<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  api,
  type SearchFilters,
  type SearchHit,
  type SearchStatus,
  type SearchWarning,
} from '@/api/client'
import AppShell from '@/components/AppShell.vue'

const route = useRoute()
const router = useRouter()

const query = ref(route.query.q as string || '')
const results = ref<SearchHit[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
const status = ref<SearchStatus>('ok')
const warnings = ref<SearchWarning[]>([])

const showFilters = ref(false)
const filters = ref<SearchFilters>({})
const entryTypes = ['article', 'book', 'inproceedings', 'phdthesis', 'techreport', 'misc']

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
    const activeFilters: SearchFilters = {}
    if (filters.value.entry_type) activeFilters.entry_type = filters.value.entry_type
    if (filters.value.year_from) activeFilters.year_from = filters.value.year_from
    if (filters.value.year_to) activeFilters.year_to = filters.value.year_to
    if (filters.value.read) activeFilters.read = filters.value.read

    const data = await api.search(query.value, activeFilters)
    status.value = data.status
    warnings.value = data.warnings
    results.value = data.hits
    total.value = data.total
  } catch (e) {
    console.error('Search failed:', e)
    error.value = 'Search failed'
    status.value = 'unavailable'
    warnings.value = []
  } finally {
    loading.value = false
  }
}

function debouncedSearch() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    router.replace({ query: { ...route.query, q: query.value } })
    search()
  }, 300)
}

watch(() => route.query, (newQuery) => {
  query.value = newQuery.q as string || ''
  search()
}, { immediate: true })

watch(query, () => { debouncedSearch() })

onUnmounted(() => { if (debounceTimer) clearTimeout(debounceTimer) })

function handleSearch() {
  router.replace({ query: { ...route.query, q: query.value } })
  search()
}

function clearFilters() {
  filters.value = {}
  search()
}

const partialWarning = computed(() => warnings.value[0]?.message ?? '')
const unavailableDetail = computed(() => {
  if (warnings.value.length === 0) return ''
  return warnings.value[warnings.value.length - 1]?.message ?? ''
})
</script>

<template>
  <AppShell title="Search">
    <template #actions>
      <button class="btn btn-ghost" @click="showFilters = !showFilters">
        {{ showFilters ? 'Hide Filters' : 'Filters' }}
      </button>
    </template>

    <!-- Search bar -->
    <form class="search-bar" @submit.prevent="handleSearch">
      <div class="search-wrapper">
        <span class="search-icon">⌕</span>
        <input
          v-model="query"
          type="text"
          class="search-input input"
          placeholder="Search papers, authors, topics..."
          autofocus
        />
      </div>
    </form>

    <div class="search-layout">
      <!-- Filters panel -->
      <aside v-if="showFilters" class="filters card">
        <div class="filter-group">
          <label class="filter-label">Type</label>
          <select v-model="filters.entry_type" class="filter-control input">
            <option value="">All types</option>
            <option v-for="t in entryTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>

        <div class="filter-group">
          <label class="filter-label">Year Range</label>
          <div class="year-range">
            <input v-model.number="filters.year_from" type="number" class="filter-control input" placeholder="From" />
            <span class="year-sep">–</span>
            <input v-model.number="filters.year_to" type="number" class="filter-control input" placeholder="To" />
          </div>
        </div>

        <div class="filter-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="filters.read" />
            Read only
          </label>
        </div>

        <div class="filter-actions">
          <button class="btn btn-primary" @click="search">Apply</button>
          <button class="btn btn-ghost" @click="clearFilters">Clear</button>
        </div>
      </aside>

      <!-- Results -->
      <section class="results">
        <div class="results-header" v-if="total > 0">
          <span class="results-count">{{ total.toLocaleString() }} results</span>
        </div>

        <div v-if="status === 'partial' && !loading && !error" class="status warning">
          <p>{{ partialWarning || 'Full-text search is unavailable. Showing degraded database results.' }}</p>
        </div>

        <div v-if="loading" class="status">
          <span class="spinner"></span>
          Searching...
        </div>
        <p v-else-if="error" class="status error">{{ error }}</p>
        <div v-else-if="status === 'unavailable'" class="status error">
          <p>Search is temporarily unavailable.</p>
          <p v-if="unavailableDetail" class="status-detail">{{ unavailableDetail }}</p>
        </div>
        <p v-else-if="results.length === 0 && query" class="status">No results found</p>
        <p v-else-if="!query" class="status empty-state">Enter a search term to find papers</p>

        <div class="results-list">
          <router-link
            v-for="item in results"
            :key="item.id"
            :to="`/entry/${item.id}`"
            class="result-row card card-hoverable"
          >
            <div class="result-body">
              <h3 class="result-title">{{ item.title }}</h3>
              <p v-if="item.authors.length" class="result-authors">{{ item.authors.join(', ') }}</p>
              <div class="result-meta">
                <span v-if="item.venue">{{ item.venue }}</span>
                <span v-if="item.year">{{ item.year }}</span>
              </div>
            </div>
            <div class="result-badges">
              <span v-if="item.has_pdf" class="badge badge-accent">PDF</span>
              <span v-if="item.read" class="badge badge-success">✓ Read</span>
            </div>
          </router-link>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.search-bar {
  margin-bottom: var(--space-5);
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: var(--space-4);
  font-size: var(--text-lg);
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  padding-left: 2.5rem;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.search-input:focus {
  box-shadow: var(--shadow-md), 0 0 0 3px var(--accent-subtle);
}

.search-layout {
  display: flex;
  gap: var(--space-6);
}

.filters {
  width: 240px;
  flex-shrink: 0;
  height: fit-content;
  position: sticky;
  top: calc(var(--header-height) + var(--space-6));
}

.filter-group {
  margin-bottom: var(--space-4);
}

.filter-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.filter-control {
  font-size: var(--text-sm);
  padding: var(--space-2) var(--space-3);
}

.year-range {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.year-sep {
  color: var(--text-muted);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  cursor: pointer;
}

.status.warning {
  color: var(--warning-strong, #8a5a00);
  background: var(--warning-bg, #fff5d6);
  border: 1px solid var(--warning-border, #f0cf72);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
}

.status-detail {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.results {
  flex: 1;
  min-width: 0;
}

.results-header {
  margin-bottom: var(--space-4);
}

.results-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.status {
  text-align: center;
  padding: var(--space-12);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}
.status.error { color: var(--danger); }

.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.result-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  text-decoration: none;
  color: inherit;
}
.result-row:hover { text-decoration: none; }

.result-body {
  flex: 1;
  min-width: 0;
}

.result-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text);
  line-height: var(--leading-tight);
  margin-bottom: var(--space-1);
}

.result-authors {
  font-size: var(--text-sm);
  color: var(--accent);
  margin-bottom: var(--space-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-meta {
  display: flex;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.result-badges {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
  margin-left: var(--space-4);
}
</style>
