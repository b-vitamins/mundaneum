<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type VenueListItem } from '@/api/client'

const route = useRoute()
const router = useRouter()

// State
const venues = ref<VenueListItem[]>([])
const loading = ref(true)
const error = ref('')

// Sorting
type SortField = 'name' | 'entry_count'
type SortOrder = 'asc' | 'desc'
type Category = 'CONFERENCE' | 'JOURNAL' | undefined

const sortBy = ref<SortField>((route.query.sort as SortField) || 'name')
const sortOrder = ref<SortOrder>((route.query.order as SortOrder) || 'asc')
const category = ref<Category>((route.query.category as Category) || undefined)

const sortOptions: { value: SortField; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'entry_count', label: 'Entry Count' },
]

const categories: { value: Category; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: 'CONFERENCE', label: 'Conferences' },
  { value: 'JOURNAL', label: 'Journals' },
]

// Actions
async function loadVenues() {
  loading.value = true
  error.value = ''
  
  try {
    venues.value = await api.listVenues(200, 0, sortBy.value, sortOrder.value, category.value)
  } catch (e) {
    console.error('Failed to load venues:', e)
    error.value = 'Failed to load venues'
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
  updateRoute()
}

function changeCategory(cat: Category) {
  category.value = cat
  updateRoute()
}

function updateRoute() {
  const query: Record<string, string | undefined> = { 
    sort: sortBy.value, 
    order: sortOrder.value 
  }
  if (category.value) {
    query.category = category.value
  }
  
  router.replace({ query })
  loadVenues()
}

onMounted(loadVenues)
</script>

<template>
  <div class="venues-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
      <h1 class="title">Venues</h1>
      <router-link to="/search" class="search-link">🔍 Search</router-link>
    </header>

    <main class="content">
      <!-- Controls -->
      <div class="controls-container">
        <!-- Category Tabs -->
        <div class="tabs">
          <button
            v-for="cat in categories"
            :key="cat.label"
            :class="['tab-btn', { active: category === cat.value }]"
            @click="changeCategory(cat.value)"
          >
            {{ cat.label }}
          </button>
        </div>

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
          <span class="count">{{ venues.length }} venues</span>
        </div>
      </div>

      <!-- Loading state -->
      <div v-if="loading" class="status">
        <span class="spinner"></span>
        Loading venues...
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="status error">{{ error }}</div>

      <!-- Empty state -->
      <div v-else-if="venues.length === 0" class="status">
        No venues found.
      </div>

      <!-- Venues grid -->
      <div v-else class="venues-grid">
        <router-link
          v-for="venue in venues"
          :key="venue.id"
          :to="`/venues/${venue.slug}`"
          class="venue-card"
        >
          <div class="venue-info">
            <span class="venue-name">{{ venue.name }}</span>
            <span class="venue-category">{{ venue.category }}</span>
          </div>
          <span class="venue-count">{{ venue.entry_count }} entries</span>
        </router-link>
      </div>
    </main>
  </div>
</template>

<style scoped>
.venues-page {
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

.controls-container {
  margin-bottom: var(--space-6);
  border-bottom: 1px solid var(--border);
}

.tabs {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.tab-btn {
  padding: var(--space-2) var(--space-1);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  font-size: var(--text-base);
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: var(--text);
}

.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 500;
}

.controls {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
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

.venues-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.venue-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: all 0.15s ease;
}

.venue-card:hover {
  border-color: var(--accent);
  text-decoration: none;
}

.venue-name {
  font-weight: 500;
  color: var(--text);
  display: block;
}

.venue-category {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  margin-top: 2px;
}

.venue-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}
</style>
