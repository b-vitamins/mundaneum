<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, type VenueDetail, type EntityEntryItem } from '@/api/client'

const route = useRoute()

// State
const venue = ref<VenueDetail | null>(null)
const entries = ref<EntityEntryItem[]>([])
const loading = ref(true)
const error = ref('')

// Load venue and entries
async function loadVenue() {
  const slug = route.params.slug as string
  loading.value = true
  error.value = ''
  
  try {
    const [venueData, entriesData] = await Promise.all([
      api.getVenue(slug),
      api.getVenueEntries(slug),
    ])
    venue.value = venueData
    entries.value = entriesData
  } catch (e) {
    console.error('Failed to load venue:', e)
    error.value = 'Venue not found'
  } finally {
    loading.value = false
  }
}

onMounted(loadVenue)

watch(() => route.params.slug, loadVenue)
</script>

<template>
  <div class="venue-detail-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
      <router-link to="/venues" class="back">← Venues</router-link>
    </header>

    <main class="content">
      <!-- Loading state -->
      <div v-if="loading" class="status">
        <span class="spinner"></span>
        Loading...
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="status error">{{ error }}</div>

      <!-- Venue content -->
      <div v-else-if="venue" class="venue-content">
        <div class="venue-header">
          <div class="venue-title-row">
            <h1 class="venue-name">{{ venue.name }}</h1>
            <span class="venue-badge">{{ venue.category }}</span>
          </div>
          
          <div v-if="venue.aliases.length > 0" class="venue-aliases">
            Known as: {{ venue.aliases.join(', ') }}
          </div>
          
          <p class="venue-stats">{{ venue.entry_count }} publications</p>
        </div>

        <section class="entries-section">
          <h2 class="section-title">Publications</h2>
          
          <div v-if="entries.length === 0" class="empty">
            No entries found in this venue.
          </div>

          <div v-else class="entries-list">
            <article v-for="entry in entries" :key="entry.id" class="entry-card">
              <router-link :to="`/entry/${entry.id}`" class="entry-title">
                {{ entry.title }}
              </router-link>
              <p class="entry-meta">
                <span class="meta-type">{{ entry.entry_type }}</span>
                <span v-if="entry.year">· {{ entry.year }}</span>
                <span v-if="entry.authors.length > 0">· {{ entry.authors[0] }}<span v-if="entry.authors.length > 1"> et al.</span></span>
              </p>
              <div class="entry-badges">
                <span v-if="entry.read" class="badge read">✓ Read</span>
              </div>
            </article>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.venue-detail-page {
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

.back {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.back:hover {
  color: var(--text);
  text-decoration: none;
}

.content {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-6);
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

.venue-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.venue-header {
  padding-bottom: var(--space-6);
  border-bottom: 1px solid var(--border);
}

.venue-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.venue-name {
  font-size: var(--text-2xl);
  font-weight: 600;
}

.venue-badge {
  font-size: 0.8rem;
  padding: 2px 8px;
  background: var(--bg-surface-2);
  border-radius: 99px;
  text-transform: uppercase;
  color: var(--text-muted);
  font-weight: 500;
}

.venue-aliases {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-2);
}

.venue-stats {
  color: var(--text-muted);
  font-size: var(--text-lg);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: 600;
  margin-bottom: var(--space-4);
}

.empty {
  color: var(--text-muted);
  padding: var(--space-6);
  text-align: center;
}

.entries-list {
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

.badge.read {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}
</style>
