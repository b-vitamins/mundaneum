<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type EntryListItem } from '@/api/client'
import AppShell from '@/components/AppShell.vue'

const route = useRoute()
const router = useRouter()

const entries = ref<EntryListItem[]>([])
const loading = ref(true)
const error = ref('')
const hasMore = ref(true)

const limit = 50
const offset = ref(0)

type SortField = 'created_at' | 'updated_at' | 'title' | 'year'
type SortOrder = 'asc' | 'desc'

const sortBy = ref<SortField>((route.query.sort as SortField) || 'created_at')
const sortOrder = ref<SortOrder>((route.query.order as SortOrder) || 'desc')

const sortOptions: { value: SortField; label: string }[] = [
  { value: 'created_at', label: 'Date Added' },
  { value: 'updated_at', label: 'Last Updated' },
  { value: 'title', label: 'Title' },
  { value: 'year', label: 'Year' },
]

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
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = field === 'title' ? 'asc' : 'desc'
  }
  router.replace({
    query: { ...route.query, sort: sortBy.value, order: sortOrder.value }
  })
  loadEntries()
}

onMounted(loadEntries)

watch(() => route.query, () => {
  sortBy.value = (route.query.sort as SortField) || 'created_at'
  sortOrder.value = (route.query.order as SortOrder) || 'desc'
}, { immediate: false })
</script>

<template>
  <AppShell title="Library" :show-search="true">
    <template #actions>
      <span class="count">{{ entries.length }} entries</span>
    </template>

    <!-- Sort controls -->
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

    <!-- Loading -->
    <div v-if="loading" class="status">
      <span class="spinner"></span>
      Loading entries...
    </div>

    <!-- Error -->
    <div v-else-if="error" class="status error">{{ error }}</div>

    <!-- Empty -->
    <div v-else-if="entries.length === 0" class="status">
      No entries in library. Add BibTeX files and run ingest.
    </div>

    <!-- Entries list -->
    <div v-else class="entries-list">
      <router-link
        v-for="entry in entries"
        :key="entry.id"
        :to="`/entry/${entry.id}`"
        class="entry-row card card-hoverable"
      >
        <div class="entry-body">
          <h3 class="entry-title">{{ entry.title }}</h3>
          <p v-if="entry.authors.length" class="entry-authors">
            {{ entry.authors.join(', ') }}
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
      </router-link>
    </div>

    <!-- Load more -->
    <div v-if="hasMore && entries.length > 0" class="load-more">
      <button class="btn btn-ghost" @click="loadMore" :disabled="loading">
        {{ loading ? 'Loading...' : 'Load More' }}
      </button>
    </div>
  </AppShell>
</template>

<style scoped>
.count {
  font-size: var(--text-sm);
  color: var(--text-muted);
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
  text-decoration: none;
  color: inherit;
}
.entry-row:hover {
  text-decoration: none;
}

.entry-body {
  min-width: 0;
  flex: 1;
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

.entry-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
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
</style>
