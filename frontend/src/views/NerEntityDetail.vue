<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import { ApiError, api } from '@/api/client'
import type { NerEntityDetail, NerEntityEntryItem } from '@/api/ner'
import { nerLabelColor } from '@/features/ner/presentation'

const route = useRoute()
const canonicalId = computed(() => route.params.id as string)

const entity = ref<NerEntityDetail | null>(null)
const entries = ref<NerEntityEntryItem[]>([])
const loading = ref(true)
const loadingEntries = ref(false)
const error = ref('')
const entriesError = ref('')
const hasMore = ref(true)
const offset = ref(0)
const limit = 50

async function loadEntity() {
  error.value = ''
  entriesError.value = ''
  entries.value = []
  offset.value = 0
  hasMore.value = true
  try {
    loading.value = true
    entity.value = await api.getEntity(canonicalId.value)
    await loadEntries()
  } catch (cause: unknown) {
    error.value = cause instanceof ApiError || cause instanceof Error
      ? cause.message
      : 'Entity not found'
  } finally {
    loading.value = false
  }
}

async function loadEntries() {
  try {
    entriesError.value = ''
    loadingEntries.value = true
    const batch = await api.getEntityEntries(canonicalId.value, limit, offset.value)
    entries.value.push(...batch)
    hasMore.value = batch.length === limit
    offset.value += batch.length
  } catch (cause: unknown) {
    entriesError.value = cause instanceof ApiError || cause instanceof Error
      ? cause.message
      : 'Failed to load related papers'
    hasMore.value = false
  } finally {
    loadingEntries.value = false
  }
}

function loadMore() {
  if (!loading.value && !loadingEntries.value && hasMore.value) {
    void loadEntries()
  }
}

onMounted(() => {
  void loadEntity()
})
watch(canonicalId, () => {
  entity.value = null
  void loadEntity()
})
</script>

<template>
  <AppShell
    :title="entity?.canonical_surface || 'Entity'"
    :back-to="'/entities'"
    :back-label="'Entities'"
    :show-search="true"
  >
    <div v-if="loading && !entity" class="status">
      <span class="spinner"></span> Loading...
    </div>
    <p v-else-if="error" class="status error">{{ error }}</p>

    <template v-if="entity">
      <!-- Header card -->
      <div class="entity-hero card">
        <div class="hero-top">
          <h2 class="entity-title">{{ entity.canonical_surface }}</h2>
          <span class="label-badge" :style="{ background: nerLabelColor(entity.label) }">{{ entity.label }}</span>
        </div>

        <div class="hero-stats">
          <div class="stat">
            <span class="stat-value">{{ entity.paper_hits.toLocaleString() }}</span>
            <span class="stat-label">Papers</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ entity.mention_total.toLocaleString() }}</span>
            <span class="stat-label">Mentions</span>
          </div>
          <div class="stat">
            <span class="stat-value">{{ entity.years_active }}</span>
            <span class="stat-label">Years Active</span>
          </div>
          <div class="stat" v-if="entity.first_year && entity.last_year">
            <span class="stat-value">{{ entity.first_year }}–{{ entity.last_year }}</span>
            <span class="stat-label">Span</span>
          </div>
        </div>

        <div class="hero-venues" v-if="entity.venues.length">
          <span class="venue-tag" v-for="v in entity.venues" :key="v">{{ v.toUpperCase() }}</span>
        </div>
      </div>

      <!-- Papers list -->
      <h3 class="section-title">Papers ({{ entity.paper_hits.toLocaleString() }})</h3>

      <div class="entries-list">
        <router-link
          v-for="item in entries"
          :key="item.id"
          :to="`/entry/${item.id}`"
          class="entry-row card card-hoverable"
        >
          <div class="entry-body">
            <h4 class="entry-title">{{ item.title }}</h4>
            <p v-if="item.authors.length" class="entry-authors">{{ item.authors.join(', ') }}</p>
            <div class="entry-meta">
              <span v-if="item.venue">{{ item.venue }}</span>
              <span v-if="item.year">{{ item.year }}</span>
              <span class="confidence">{{ (item.confidence * 100).toFixed(0) }}% conf</span>
            </div>
          </div>
        </router-link>
      </div>
      <p v-if="entriesError" class="entries-error">{{ entriesError }}</p>

      <div v-if="hasMore && !loading" class="load-more">
        <button class="btn btn-ghost" @click="loadMore">Load more</button>
      </div>
      <div v-if="loadingEntries && entries.length > 0" class="status">
        <span class="spinner"></span> Loading...
      </div>
    </template>
  </AppShell>
</template>

<style scoped>
.entity-hero {
  margin-bottom: var(--space-6);
}

.hero-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.entity-title {
  font-size: var(--text-xl);
  font-weight: 600;
  text-transform: capitalize;
}

.label-badge {
  flex-shrink: 0;
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full, 999px);
  font-size: var(--text-sm);
  font-weight: 600;
  color: #fff;
  text-transform: capitalize;
}

.hero-stats {
  display: flex;
  gap: var(--space-6);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}

.stat {
  display: flex;
  flex-direction: column;
}
.stat-value {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text);
}
.stat-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.hero-venues {
  display: flex;
  gap: var(--space-2);
}
.venue-tag {
  padding: 2px var(--space-2);
  border-radius: var(--radius);
  font-size: var(--text-xs);
  font-weight: 600;
  background: var(--surface-elevated, var(--surface));
  color: var(--text-secondary);
  letter-spacing: 0.05em;
}

.section-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-4);
}

.entries-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.entry-row {
  text-decoration: none;
  color: inherit;
}
.entry-row:hover { text-decoration: none; }

.entry-body {
  min-width: 0;
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
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.entries-error {
  margin-top: var(--space-3);
  color: var(--danger);
  font-size: var(--text-sm);
}

.confidence {
  opacity: 0.7;
}

.load-more {
  text-align: center;
  padding: var(--space-6);
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
</style>
