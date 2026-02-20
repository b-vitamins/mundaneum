<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, type VenueDetail, type EntityEntryItem } from '@/api/client'
import AppShell from '@/components/AppShell.vue'

const route = useRoute()
const venue = ref<VenueDetail | null>(null)
const entries = ref<EntityEntryItem[]>([])
const loading = ref(true)
const error = ref('')

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
  <AppShell back-to="/venues" back-label="Venues" :title="venue?.name || 'Venue'">
    <div v-if="loading" class="status"><span class="spinner"></span> Loading...</div>
    <div v-else-if="error" class="status error">{{ error }}</div>

    <div v-else-if="venue" class="detail-content">
      <div class="detail-header">
        <div class="title-row">
          <h1 class="detail-name">{{ venue.name }}</h1>
          <span class="badge badge-muted">{{ venue.category }}</span>
        </div>
        <p v-if="venue.aliases.length > 0" class="aliases">Also known as: {{ venue.aliases.join(', ') }}</p>
        <p class="detail-stats">{{ venue.entry_count }} publications</p>
      </div>

      <section>
        <h2 class="section-title">Publications</h2>
        <div v-if="entries.length === 0" class="empty">No entries found.</div>
        <div v-else class="entries-list">
          <router-link
            v-for="entry in entries"
            :key="entry.id"
            :to="`/entry/${entry.id}`"
            class="entry-row card card-hoverable"
          >
            <div class="entry-body">
              <h3 class="entry-title">{{ entry.title }}</h3>
              <p class="entry-meta">
                <span class="badge badge-muted">{{ entry.entry_type }}</span>
                <span v-if="entry.year">{{ entry.year }}</span>
                <span v-if="entry.authors.length > 0">{{ entry.authors[0] }}<span v-if="entry.authors.length > 1"> et al.</span></span>
              </p>
            </div>
            <span v-if="entry.read" class="badge badge-success">✓ Read</span>
          </router-link>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.status {
  text-align: center; padding: var(--space-12); color: var(--text-muted);
  display: flex; align-items: center; justify-content: center; gap: var(--space-2);
}
.status.error { color: var(--danger); }
.detail-content { display: flex; flex-direction: column; gap: var(--space-8); }
.detail-header { padding-bottom: var(--space-6); border-bottom: 1px solid var(--border-subtle); }
.title-row { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-1); }
.detail-name { font-size: var(--text-2xl); font-weight: 600; }
.aliases { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-1); }
.detail-stats { color: var(--text-muted); font-size: var(--text-base); }
.section-title { font-size: var(--text-lg); font-weight: 600; margin-bottom: var(--space-4); }
.empty { color: var(--text-muted); padding: var(--space-8); text-align: center; }
.entries-list { display: flex; flex-direction: column; gap: var(--space-3); }
.entry-row {
  display: flex; justify-content: space-between; align-items: flex-start;
  text-decoration: none; color: inherit;
}
.entry-row:hover { text-decoration: none; }
.entry-body { flex: 1; min-width: 0; }
.entry-title { font-size: var(--text-base); font-weight: 500; color: var(--text); margin-bottom: var(--space-1); }
.entry-meta { display: flex; gap: var(--space-2); font-size: var(--text-sm); color: var(--text-muted); align-items: center; }
</style>
