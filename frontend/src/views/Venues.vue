<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type VenueListItem } from '@/api/client'
import AppShell from '@/components/AppShell.vue'

const route = useRoute()
const router = useRouter()

const venues = ref<VenueListItem[]>([])
const loading = ref(true)
const error = ref('')

type SortField = 'name' | 'entry_count'
type SortOrder = 'asc' | 'desc'
type Category = 'CONFERENCE' | 'JOURNAL' | undefined

const sortBy = ref<SortField>((route.query.sort as SortField) || 'name')
const sortOrder = ref<SortOrder>((route.query.order as SortOrder) || 'asc')
const category = ref<Category>((route.query.category as Category) || undefined)

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
    order: sortOrder.value,
  }
  if (category.value) query.category = category.value
  router.replace({ query })
  loadVenues()
}

onMounted(loadVenues)
</script>

<template>
  <AppShell title="Venues" :show-search="true">
    <template #actions>
      <span class="count">{{ venues.length }} venues</span>
    </template>

    <div class="controls">
      <!-- Category segmented control -->
      <div class="segmented">
        <button
          v-for="cat in [
            { value: undefined, label: 'All' },
            { value: 'CONFERENCE', label: 'Conferences' },
            { value: 'JOURNAL', label: 'Journals' },
          ]"
          :key="cat.label"
          :class="['segmented-item', { active: category === cat.value }]"
          @click="changeCategory(cat.value as Category)"
        >{{ cat.label }}</button>
      </div>

      <!-- Sort segmented control -->
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
      Loading venues...
    </div>
    <div v-else-if="error" class="status error">{{ error }}</div>
    <div v-else-if="venues.length === 0" class="status">No venues found.</div>

    <div v-else class="venues-grid">
      <router-link
        v-for="venue in venues"
        :key="venue.id"
        :to="`/venues/${venue.slug}`"
        class="venue-card card card-hoverable"
      >
        <div class="venue-info">
          <span class="venue-name">{{ venue.name }}</span>
          <span class="venue-category badge badge-muted">{{ venue.category }}</span>
        </div>
        <span class="venue-count">{{ venue.entry_count }}</span>
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
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
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

.venues-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.venue-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-decoration: none;
  color: inherit;
}
.venue-card:hover { text-decoration: none; }

.venue-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.venue-name {
  font-weight: 500;
  color: var(--text);
  font-size: var(--text-sm);
}

.venue-category {
  font-size: var(--text-xs);
  text-transform: uppercase;
}

.venue-count {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-secondary);
}
</style>
