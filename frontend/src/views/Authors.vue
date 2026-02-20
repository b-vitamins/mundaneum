<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type AuthorListItem } from '@/api/client'
import AppShell from '@/components/AppShell.vue'

const route = useRoute()
const router = useRouter()

const authors = ref<AuthorListItem[]>([])
const loading = ref(true)
const error = ref('')

type SortField = 'name' | 'entry_count'
type SortOrder = 'asc' | 'desc'

const sortBy = ref<SortField>((route.query.sort as SortField) || 'name')
const sortOrder = ref<SortOrder>((route.query.order as SortOrder) || 'asc')

async function loadAuthors() {
  loading.value = true
  error.value = ''
  try {
    authors.value = await api.listAuthors(200, 0, sortBy.value, sortOrder.value)
  } catch (e) {
    console.error('Failed to load authors:', e)
    error.value = 'Failed to load authors'
  } finally {
    loading.value = false
  }
}

function changeSort(field: SortField) {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = field === 'entry_count' ? 'desc' : 'asc'
  }
  router.replace({ query: { ...route.query, sort: sortBy.value, order: sortOrder.value } })
  loadAuthors()
}

onMounted(loadAuthors)
</script>

<template>
  <AppShell title="Authors" :show-search="true">
    <template #actions>
      <span class="count">{{ authors.length }} authors</span>
    </template>

    <div class="controls">
      <div class="segmented">
        <button
          :class="['segmented-item', { active: sortBy === 'name' }]"
          @click="changeSort('name')"
        >Name</button>
        <button
          :class="['segmented-item', { active: sortBy === 'entry_count' }]"
          @click="changeSort('entry_count')"
        >Entry Count</button>
      </div>
    </div>

    <div v-if="loading" class="status">
      <span class="spinner"></span>
      Loading authors...
    </div>
    <div v-else-if="error" class="status error">{{ error }}</div>
    <div v-else-if="authors.length === 0" class="status">No authors found.</div>

    <div v-else class="authors-grid">
      <router-link
        v-for="author in authors"
        :key="author.id"
        :to="`/authors/${author.id}`"
        class="author-card card card-hoverable"
      >
        <span class="author-name">{{ author.name }}</span>
        <span class="author-count badge badge-muted">{{ author.entry_count }}</span>
      </router-link>
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

.authors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-3);
}

.author-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-decoration: none;
  color: inherit;
}
.author-card:hover { text-decoration: none; }

.author-name {
  font-weight: 500;
  color: var(--text);
  font-size: var(--text-sm);
}

.author-count {
  flex-shrink: 0;
}
</style>
