<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type AuthorRef, type EntryListItem } from '@/api/client'
import AppShell from '@/components/AppShell.vue'
import { ENTRY_TYPES } from '@/constants'
import {
  buildSearchFilters,
  buildSearchRouteQuery,
  defaultSearchFilters,
  readSearchQuery,
  type SearchFilterForm,
} from '@/features/search/model'

const route = useRoute()
const router = useRouter()

const entries = ref<EntryListItem[]>([])
const loading = ref(true)
const error = ref('')
const hasMore = ref(true)
const totalEntries = ref(0)
const showFilters = ref(false)

const limit = 50
const offset = ref(0)

type SortField = 'created_at' | 'updated_at' | 'title' | 'year'
type SortOrder = 'asc' | 'desc'

function isSortField(value: unknown): value is SortField {
  return value === 'created_at' || value === 'updated_at' || value === 'title' || value === 'year'
}

function isSortOrder(value: unknown): value is SortOrder {
  return value === 'asc' || value === 'desc'
}

const sortBy = ref<SortField>(isSortField(route.query.sort) ? route.query.sort : 'created_at')
const sortOrder = ref<SortOrder>(isSortOrder(route.query.order) ? route.query.order : 'desc')
const filters = ref<SearchFilterForm>(readSearchQuery(route.query).filters)

const sortOptions: { value: SortField; label: string }[] = [
  { value: 'created_at', label: 'Date Added' },
  { value: 'updated_at', label: 'Last Updated' },
  { value: 'title', label: 'Title' },
  { value: 'year', label: 'Year' },
]

const activeFilterCount = computed(() => Object.keys(buildSearchFilters(filters.value)).length)
const countLabel = computed(() => {
  const noun = activeFilterCount.value > 0 ? 'matching entries' : 'entries'
  if (totalEntries.value > 0) {
    return `Showing ${entries.value.length.toLocaleString()} of ${totalEntries.value.toLocaleString()} ${noun}`
  }
  return `${entries.value.length.toLocaleString()} ${noun}`
})

function browseAuthorRefs(entry: EntryListItem): Array<AuthorRef | { id?: undefined; name: string }> {
  const authorRefs = entry.author_refs ?? []
  if (authorRefs.length > 0) return authorRefs
  return entry.authors.map((name) => ({ name }))
}

async function loadEntries(append = false) {
  if (!append) {
    loading.value = true
    offset.value = 0
    entries.value = []
  }
  error.value = ''
  try {
    const result = await api.listEntries(
      limit,
      offset.value,
      sortBy.value,
      sortOrder.value,
      buildSearchFilters(filters.value)
    )
    totalEntries.value = result.total
    if (append) {
      entries.value = [...entries.value, ...result.items]
    } else {
      entries.value = result.items
    }
    hasMore.value = entries.value.length < result.total
  } catch (e) {
    console.error('Failed to load entries:', e)
    error.value = 'Failed to load entries'
  } finally {
    loading.value = false
  }
}

function syncRoute() {
  router.replace({
    query: {
      ...buildSearchRouteQuery('', filters.value),
      sort: sortBy.value,
      order: sortOrder.value,
    }
  })
}

function loadMore() {
  offset.value += limit
  void loadEntries(true)
}

function changeSort(field: SortField) {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = field === 'title' ? 'asc' : 'desc'
  }
  syncRoute()
}

function applyFilters() {
  syncRoute()
}

function clearFilters() {
  filters.value = defaultSearchFilters()
  syncRoute()
}

watch(
  () => route.query,
  () => {
    sortBy.value = isSortField(route.query.sort) ? route.query.sort : 'created_at'
    sortOrder.value = isSortOrder(route.query.order) ? route.query.order : 'desc'
    filters.value = readSearchQuery(route.query).filters
    void loadEntries()
  },
  { immediate: true }
)
</script>

<template>
  <AppShell title="Library" :show-search="true">
    <template #actions>
      <div class="header-actions">
        <button class="btn btn-ghost" @click="showFilters = !showFilters">
          {{ showFilters ? 'Hide Filters' : 'Filters' }}
          <span v-if="activeFilterCount > 0">({{ activeFilterCount }})</span>
        </button>
        <span v-if="!loading" class="count">{{ countLabel }}</span>
      </div>
    </template>

    <div class="browse-layout">
      <aside v-if="showFilters" class="filters card">
        <div class="filter-group">
          <label class="filter-label">Type</label>
          <select v-model="filters.entry_type" class="filter-control input">
            <option value="">All types</option>
            <option v-for="type in ENTRY_TYPES" :key="type" :value="type">{{ type }}</option>
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
          <label class="filter-label">PDF</label>
          <select v-model="filters.has_pdf" class="filter-control input">
            <option value="">Any</option>
            <option value="true">Attached</option>
            <option value="false">Missing</option>
          </select>
        </div>

        <div class="filter-group">
          <label class="filter-label">Read status</label>
          <select v-model="filters.read" class="filter-control input">
            <option value="">Any</option>
            <option value="true">Read</option>
            <option value="false">Unread</option>
          </select>
        </div>

        <div class="filter-actions">
          <button type="button" class="btn btn-primary" @click="applyFilters">Apply</button>
          <button type="button" class="btn btn-ghost" @click="clearFilters">Clear</button>
        </div>
      </aside>

      <section class="browse-results">
        <div class="controls">
          <div class="segmented">
            <button
              v-for="opt in sortOptions"
              :key="opt.value"
              :class="['segmented-item', { active: sortBy === opt.value }]"
              @click="changeSort(opt.value)"
            >
              {{ opt.label }}
              <span v-if="sortBy === opt.value" class="sort-arrow">
                {{ sortOrder === 'desc' ? '↓' : '↑' }}
              </span>
            </button>
          </div>
        </div>

        <div v-if="loading" class="status">
          <span class="spinner"></span>
          Loading entries...
        </div>

        <div v-else-if="error" class="status error">{{ error }}</div>

        <div v-else-if="entries.length === 0" class="status">
          {{ activeFilterCount > 0 ? 'No entries match the current filters.' : 'No entries in library. Add BibTeX files and run ingest.' }}
        </div>

        <div v-else class="entries-list">
          <article
            v-for="entry in entries"
            :key="entry.id"
            class="entry-row card card-hoverable"
          >
            <div class="entry-body">
              <router-link :to="`/entry/${entry.id}`" class="entry-title-link">
                <h3 class="entry-title">{{ entry.title }}</h3>
              </router-link>
              <p v-if="entry.authors.length" class="entry-authors">
                <template v-for="(author, index) in browseAuthorRefs(entry)" :key="`${entry.id}-${author.name}-${index}`">
                  <router-link
                    v-if="author.id"
                    :to="{ name: 'author-detail', params: { id: author.id } }"
                    class="entry-author-link"
                  >
                    {{ author.name }}
                  </router-link>
                  <span v-else>{{ author.name }}</span>
                  <span v-if="index < entry.authors.length - 1">, </span>
                </template>
              </p>
              <div class="entry-meta">
                <span v-if="entry.venue" class="venue">{{ entry.venue }}</span>
                <span v-if="entry.year" class="year">{{ entry.year }}</span>
                <span class="type badge badge-muted">{{ entry.entry_type }}</span>
              </div>
            </div>
            <div class="entry-badges">
              <span v-if="entry.file_path" class="badge badge-accent">PDF</span>
              <span v-if="entry.read" class="badge badge-success">✓ Read</span>
            </div>
          </article>
        </div>

        <div v-if="hasMore && entries.length > 0" class="load-more">
          <button class="btn btn-ghost" @click="loadMore" :disabled="loading">
            {{ loading ? 'Loading...' : 'Load More' }}
          </button>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.browse-layout {
  display: flex;
  gap: var(--space-6);
}

.browse-results {
  flex: 1;
  min-width: 0;
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

.year-range .filter-control {
  min-width: 80px;
}

.year-sep {
  color: var(--text-muted);
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
}

.controls {
  margin-bottom: var(--space-5);
}

.sort-arrow {
  margin-left: 2px;
  font-size: var(--text-xs);
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
.status.error {
  color: var(--danger);
}

.entries-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.entry-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.entry-body {
  min-width: 0;
  flex: 1;
}

.entry-title-link {
  color: inherit;
}

.entry-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text);
  line-height: var(--leading-tight);
  margin-bottom: var(--space-1);
}

.entry-authors {
  font-size: var(--text-sm);
  color: var(--accent);
  margin-bottom: var(--space-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.entry-author-link {
  color: inherit;
}

.entry-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
  flex-wrap: wrap;
}

.entry-badges {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
  margin-left: var(--space-4);
}

.load-more {
  text-align: center;
  padding: var(--space-6);
}

@media (max-width: 900px) {
  .browse-layout {
    flex-direction: column;
  }

  .filters {
    width: 100%;
    position: static;
  }

  .header-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}
</style>
