<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type TopicListItem } from '@/api/client'

const route = useRoute()
const router = useRouter()

// State
const topics = ref<TopicListItem[]>([])
const loading = ref(true)
const error = ref('')

// Sorting
type SortField = 'name' | 'entry_count'
type SortOrder = 'asc' | 'desc'

const sortBy = ref<SortField>((route.query.sort as SortField) || 'name')
const sortOrder = ref<SortOrder>((route.query.order as SortOrder) || 'asc')

const sortOptions: { value: SortField; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'entry_count', label: 'Entry Count' },
]

// Actions
async function loadTopics() {
  loading.value = true
  error.value = ''
  
  try {
    topics.value = await api.listTopics(200, 0, sortBy.value, sortOrder.value)
  } catch (e) {
    console.error('Failed to load topics:', e)
    error.value = 'Failed to load topics'
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
  
  router.replace({ 
    query: { ...route.query, sort: sortBy.value, order: sortOrder.value } 
  })
  
  loadTopics()
}

onMounted(loadTopics)
</script>

<template>
  <div class="topics-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
      <h1 class="title">Curated Topics</h1>
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
        <span class="count">{{ topics.length }} topics</span>
      </div>

      <!-- Loading state -->
      <div v-if="loading" class="status">
        <span class="spinner"></span>
        Loading topics...
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="status error">{{ error }}</div>

      <!-- Empty state -->
      <div v-else-if="topics.length === 0" class="status">
        No topics found.
      </div>

      <!-- Topics grid -->
      <div v-else class="topics-grid">
        <router-link
          v-for="topic in topics"
          :key="topic.id"
          :to="`/topics/${topic.slug}`"
          class="topic-card"
        >
          <span class="topic-name">{{ topic.name }}</span>
          <span class="topic-count">{{ topic.entry_count }} entries</span>
        </router-link>
      </div>
    </main>
  </div>
</template>

<style scoped>
.topics-page {
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

.topics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.topic-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: all 0.15s ease;
}

.topic-card:hover {
  border-color: var(--accent);
  text-decoration: none;
}

.topic-name {
  font-weight: 500;
  color: var(--text);
}

.topic-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}
</style>
