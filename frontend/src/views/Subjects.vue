<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type SubjectListItem } from '@/api/client'

const route = useRoute()
const router = useRouter()

// State
const subjects = ref<SubjectListItem[]>([])
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
async function loadSubjects() {
  loading.value = true
  error.value = ''
  
  try {
    subjects.value = await api.listSubjects(200, 0, sortBy.value, sortOrder.value)
  } catch (e) {
    console.error('Failed to load subjects:', e)
    error.value = 'Failed to load subjects'
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
  
  loadSubjects()
}

onMounted(loadSubjects)
</script>

<template>
  <div class="subjects-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
      <h1 class="title">Subject Areas</h1>
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
        <span class="count">{{ subjects.length }} subjects</span>
      </div>

      <!-- Loading state -->
      <div v-if="loading" class="status">
        <span class="spinner"></span>
        Loading subjects...
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="status error">{{ error }}</div>

      <!-- Empty state -->
      <div v-else-if="subjects.length === 0" class="status">
        No subjects found.
      </div>

      <!-- Subjects grid -->
      <div v-else class="subjects-grid">
        <router-link
          v-for="subject in subjects"
          :key="subject.id"
          :to="`/subjects/${subject.slug}`"
          class="subject-card"
        >
          <span class="subject-name">{{ subject.name }}</span>
          <span class="subject-count">{{ subject.entry_count }} entries</span>
        </router-link>
      </div>
    </main>
  </div>
</template>

<style scoped>
.subjects-page {
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

.subjects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.subject-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: all 0.15s ease;
}

.subject-card:hover {
  border-color: var(--accent);
  text-decoration: none;
}

.subject-name {
  font-weight: 500;
  color: var(--text);
}

.subject-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}
</style>
