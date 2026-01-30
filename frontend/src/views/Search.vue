<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type SearchHit, type SearchFilters } from '@/api/client'

const route = useRoute()
const router = useRouter()

const query = ref(route.query.q as string || '')
const results = ref<SearchHit[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

// Filters
const showFilters = ref(false)
const filters = ref<SearchFilters>({})
const entryTypes = ['article', 'book', 'inproceedings', 'phdthesis', 'techreport', 'misc']

// Debounce timer
let debounceTimer: ReturnType<typeof setTimeout> | null = null

const search = async () => {
  if (!query.value.trim()) return
  
  loading.value = true
  error.value = ''
  
  try {
    const response = await api.search(query.value, filters.value)
    results.value = response.hits
    total.value = response.total
  } catch (e) {
    console.error('Search failed:', e)
    error.value = 'Search failed. Please try again.'
    results.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

// Debounced search
const debouncedSearch = () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(search, 300)
}

watch(() => route.query.q, (newQ) => {
  query.value = newQ as string || ''
  if (query.value) search()
}, { immediate: true })

// Watch query for debounced search on typing
watch(query, () => {
  if (query.value.trim()) {
    debouncedSearch()
  }
})

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

const handleSearch = () => {
  router.push({ name: 'search', query: { q: query.value } })
}

const toggleFilters = () => {
  showFilters.value = !showFilters.value
}

const applyFilters = () => {
  search()
}

const clearFilters = () => {
  filters.value = {}
  search()
}
</script>

<template>
  <div class="search-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
      <form class="search-form" @submit.prevent="handleSearch">
        <input
          v-model="query"
          type="text"
          class="search-input"
          placeholder="Search..."
        />
      </form>
      <button class="filter-toggle" @click="toggleFilters">
        {{ showFilters ? 'Hide Filters' : 'Filters' }}
      </button>
    </header>

    <main class="content">
      <aside v-if="showFilters" class="filters">
        <div class="filter-group">
          <label class="filter-label">Type</label>
          <select v-model="filters.entry_type" class="filter-select">
            <option value="">All types</option>
            <option v-for="t in entryTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>

        <div class="filter-group">
          <label class="filter-label">Year</label>
          <div class="year-range">
            <input
              v-model.number="filters.year_from"
              type="number"
              class="filter-input"
              placeholder="From"
            />
            <span class="range-sep">–</span>
            <input
              v-model.number="filters.year_to"
              type="number"
              class="filter-input"
              placeholder="To"
            />
          </div>
        </div>

        <div class="filter-group">
          <label class="filter-checkbox">
            <input type="checkbox" v-model="filters.has_pdf" />
            Has PDF
          </label>
        </div>

        <div class="filter-group">
          <label class="filter-checkbox">
            <input type="checkbox" v-model="filters.read" />
            Read only
          </label>
        </div>

        <div class="filter-actions">
          <button class="btn-apply" @click="applyFilters">Apply</button>
          <button class="btn-clear" @click="clearFilters">Clear</button>
        </div>
      </aside>

      <section class="results">
        <div class="results-header">
          <span v-if="total > 0" class="results-count">{{ total.toLocaleString() }} results</span>
        </div>

        <p v-if="loading" class="status">
          <span class="spinner"></span>
          Searching...
        </p>
        <p v-else-if="error" class="status error">{{ error }}</p>
        <p v-else-if="results.length === 0 && query" class="status">No results found</p>
        <p v-else-if="!query" class="status">Enter a search term</p>

        <article v-for="item in results" :key="item.id" class="result-card">
          <router-link :to="`/entry/${item.id}`" class="result-title">
            {{ item.title }}
          </router-link>
          <p class="result-authors">{{ item.authors.join(', ') }}</p>
          <p class="result-meta">
            <span class="meta-type">{{ item.entry_type }}</span>
            <span v-if="item.year">· {{ item.year }}</span>
            <span v-if="item.venue">· {{ item.venue }}</span>
          </p>
          <p v-if="item.abstract" class="result-abstract">
            {{ item.abstract.slice(0, 200) }}{{ item.abstract.length > 200 ? '...' : '' }}
          </p>
          <div class="result-actions">
            <router-link 
              v-if="item.has_pdf" 
              class="action-link" 
              :to="`/entry/${item.id}`"
              @click.stop
            >
              PDF
            </router-link>
            <span v-if="item.read" class="read-badge">✓ Read</span>
          </div>
        </article>
      </section>
    </main>
  </div>
</template>

<style scoped>
.search-page {
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}

.brand {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.search-form {
  flex: 1;
  max-width: 600px;
}

.search-input {
  width: 100%;
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
}

.filter-toggle {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.filter-toggle:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.content {
  display: flex;
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-6);
  gap: var(--space-8);
}

.filters {
  width: 220px;
  flex-shrink: 0;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  height: fit-content;
}

.filter-group {
  margin-bottom: var(--space-4);
}

.filter-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  margin-bottom: var(--space-2);
}

.filter-select,
.filter-input {
  width: 100%;
  padding: var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font-size: var(--text-sm);
}

.year-range {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.range-sep {
  color: var(--text-muted);
}

.filter-checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text);
  cursor: pointer;
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border);
}

.btn-apply {
  flex: 1;
  padding: var(--space-2);
  background: var(--accent);
  color: white;
  border-radius: var(--radius);
  font-size: var(--text-sm);
}

.btn-clear {
  padding: var(--space-2);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.results {
  flex: 1;
}

.results-header {
  margin-bottom: var(--space-4);
}

.results-count {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.status {
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-8);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

.status.error {
  color: #ef4444;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.result-card {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
}

.result-card:hover {
  background: var(--bg-surface);
}

.result-title {
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--text);
  display: block;
  margin-bottom: var(--space-1);
}

.result-authors {
  color: var(--accent);
  font-size: var(--text-sm);
  margin-bottom: var(--space-1);
}

.result-meta {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-2);
}

.meta-type {
  text-transform: uppercase;
  font-size: 0.7rem;
  padding: 2px 6px;
  background: var(--border);
  border-radius: 4px;
}

.result-abstract {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.5;
  margin-bottom: var(--space-2);
}

.result-actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.action-link {
  font-size: var(--text-sm);
  color: var(--accent);
}

.read-badge {
  font-size: var(--text-sm);
  color: var(--text-muted);
}
</style>
