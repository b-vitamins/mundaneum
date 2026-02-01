<script setup lang="ts">
import { ref, watch, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type EntryListItem } from '@/api/client'

const route = useRoute()
const router = useRouter()

// State
const entries = ref<EntryListItem[]>([])
const loading = ref(true)
const error = ref('')
const hasMore = ref(true)

// Pagination
const limit = 50
const offset = ref(0)

// Sorting
type SortField = 'created_at' | 'title' | 'year' | 'updated_at'
type SortOrder = 'asc' | 'desc'

const sortBy = ref<SortField>((route.query.sort as SortField) || 'created_at')
const sortOrder = ref<SortOrder>((route.query.order as SortOrder) || 'desc')

const sortOptions: { value: SortField; label: string }[] = [
  { value: 'created_at', label: 'Date Added' },
  { value: 'updated_at', label: 'Last Updated' },
  { value: 'title', label: 'Title' },
  { value: 'year', label: 'Year' },
]

// Computed
const sortLabel = computed(() => {
  const opt = sortOptions.find(o => o.value === sortBy.value)
  return opt?.label || 'Date Added'
})

// Actions
async function loadEntries(append = false) {
  if (!append) {
    loading.value = true
    offset.value = 0
    entries.value = []
  }
  
  error.value = ''
  
  try {
    const data = await api.listEntries(limit, offset.value, sortBy.value, sortOrder.value)
    
    if (append) {
      entries.value = [...entries.value, ...data]
    } else {
      entries.value = data
    }
    
    hasMore.value = data.length === limit
  } catch (e) {
    console.error('Failed to load entries:', e)
    error.value = 'Failed to load entries'
  } finally {
    loading.value = false
  }
}

function loadMore() {
  offset.value += limit
  loadEntries(true)
}

function changeSort(field: SortField) {
  if (sortBy.value === field) {
    // Toggle order
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = 'desc'
  }
  
  // Update URL
  router.replace({ 
    query: { ...route.query, sort: sortBy.value, order: sortOrder.value } 
  })
  
  loadEntries()
}

// Initial load and watch for route changes
onMounted(loadEntries)

watch(() => route.query, () => {
  sortBy.value = (route.query.sort as SortField) || 'created_at'
  sortOrder.value = (route.query.order as SortOrder) || 'desc'
}, { immediate: false })
</script>

<template>
  <div class="browse-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
      <h1 class="title">Browse Library</h1>
      <router-link to="/search" class="search-link">🔍 Search</router-link>
    </header>

    <main class="content">
      <!-- Sort controls -->
      <div class="controls">
        <span class="sort-label">Sort by:</span>
        <div class="sort-buttons">
          <button
            v-for="opt in sortOptions"
            :key="opt.value"
            :class="['sort-btn', { active: sortBy === opt.value }]"
            @click="changeSort(opt.value)"
          >
            {{ opt.label }}
            <span v-if="sortBy === opt.value" class="sort-arrow">
              {{ sortOrder === 'desc' ? '↓' : '↑' }}
            </span>
          </button>
        </div>
        <span class="count">{{ entries.length }} entries</span>
      </div>

      <!-- Loading state -->
      <div v-if="loading && entries.length === 0" class="status">
        <span class="spinner"></span>
        Loading entries...
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="status error">{{ error }}</div>

      <!-- Empty state -->
      <div v-else-if="entries.length === 0" class="status">
        No entries in library. Add BibTeX files and run ingest.
      </div>

      <!-- Entries list -->
      <div v-else class="entries-grid">
        <article v-for="entry in entries" :key="entry.id" class="entry-card">
          <router-link :to="`/entry/${entry.id}`" class="entry-title">
            {{ entry.title }}
          </router-link>
          <p class="entry-authors">{{ entry.authors.join(', ') }}</p>
          <p class="entry-meta">
            <span class="meta-type">{{ entry.entry_type }}</span>
            <span v-if="entry.year">· {{ entry.year }}</span>
            <span v-if="entry.venue">· {{ entry.venue }}</span>
          </p>
          <div class="entry-badges">
            <span v-if="entry.file_path" class="badge pdf">PDF</span>
            <span v-if="entry.read" class="badge read">✓ Read</span>
          </div>
        </article>
      </div>

      <!-- Load more button -->
      <div v-if="hasMore && entries.length > 0" class="load-more">
        <button class="load-more-btn" @click="loadMore" :disabled="loading">
          {{ loading ? 'Loading...' : 'Load More' }}
        </button>
      </div>
    </main>
  </div>
</template>

<style scoped>
.browse-page {
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

.title {
  flex: 1;
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--text-muted);
}

.search-link {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.search-link:hover {
  color: var(--text);
  border-color: var(--text-muted);
  text-decoration: none;
}

.content {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-6);
}

.controls {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}

.sort-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.sort-buttons {
  display: flex;
  gap: var(--space-2);
}

.sort-btn {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: transparent;
  color: var(--text-muted);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.sort-btn:hover {
  color: var(--text);
  border-color: var(--text-muted);
}

.sort-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.sort-arrow {
  margin-left: var(--space-1);
}

.count {
  margin-left: auto;
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.status {
  text-align: center;
  padding: var(--space-8);
  color: var(--text-muted);
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

.entries-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.entry-card {
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
  transition: background 0.15s ease;
}

.entry-card:hover {
  background: var(--bg-surface);
}

.entry-title {
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--text);
  display: block;
  margin-bottom: var(--space-1);
}

.entry-title:hover {
  color: var(--accent);
  text-decoration: none;
}

.entry-authors {
  color: var(--accent);
  font-size: var(--text-sm);
  margin-bottom: var(--space-1);
}

.entry-meta {
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

.entry-badges {
  display: flex;
  gap: var(--space-2);
}

.badge {
  font-size: var(--text-xs);
  padding: 2px 6px;
  border-radius: 4px;
}

.badge.pdf {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.badge.read {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.load-more {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
}

.load-more-btn {
  padding: var(--space-3) var(--space-6);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s ease;
}

.load-more-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.load-more-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
