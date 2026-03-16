<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import AppShell from '@/components/AppShell.vue'
import { ApiError, api } from '@/api/client'
import type { NerEntityLabelStat, NerEntityListItem } from '@/api/ner'
import { nerLabelColor } from '@/features/ner/presentation'

const entities = ref<NerEntityListItem[]>([])
const labelStats = ref<NerEntityLabelStat[]>([])
const loading = ref(true)
const error = ref('')
const hasMore = ref(true)
const selectedLabel = ref('')

const limit = 50
const offset = ref(0)

async function loadEntities() {
  try {
    error.value = ''
    const batch = await api.listEntities(
      limit,
      offset.value,
      'paper_hits',
      'desc',
      selectedLabel.value || undefined,
    )
    entities.value.push(...batch)
    hasMore.value = batch.length === limit
    offset.value += batch.length
  } catch (cause: unknown) {
    error.value = cause instanceof ApiError || cause instanceof Error
      ? cause.message
      : 'Failed to load entities'
  } finally {
    loading.value = false
  }
}

async function reloadEntities() {
  entities.value = []
  offset.value = 0
  hasMore.value = true
  loading.value = true
  await loadEntities()
}

async function loadLabelStats() {
  try {
    error.value = ''
    labelStats.value = await api.listEntityLabels()
  } catch (cause: unknown) {
    error.value = cause instanceof ApiError || cause instanceof Error
      ? cause.message
      : 'Failed to load entity labels'
  }
}

function loadMore() {
  if (!loading.value && hasMore.value) {
    loading.value = true
    void loadEntities()
  }
}

watch(selectedLabel, () => {
  void reloadEntities()
})

onMounted(async () => {
  loading.value = true
  await Promise.all([loadLabelStats(), reloadEntities()])
  loading.value = false
})
</script>

<template>
  <AppShell title="Entities" :show-search="true">
    <template #actions>
      <span v-if="!loading" class="count">{{ entities.length.toLocaleString() }} entities</span>
    </template>

    <div class="controls" v-if="labelStats.length > 0">
      <div class="label-filter">
        <button
          class="label-chip"
          :class="{ active: !selectedLabel }"
          @click="selectedLabel = ''"
        >All</button>
        <button
          v-for="stat in labelStats"
          :key="stat.label"
          class="label-chip"
          :class="{ active: selectedLabel === stat.label }"
          :style="selectedLabel === stat.label ? { background: nerLabelColor(stat.label), color: '#fff' } : {}"
          @click="selectedLabel = stat.label"
        >{{ stat.label }}</button>
      </div>
    </div>

    <div v-if="loading && entities.length === 0" class="status">
      <span class="spinner"></span> Loading entities...
    </div>
    <p v-else-if="error" class="status error">{{ error }}</p>

    <div class="entity-grid">
      <router-link
        v-for="e in entities"
        :key="e.canonical_id"
        :to="`/entities/${e.canonical_id}`"
        class="entity-card card card-hoverable"
      >
        <div class="entity-header">
          <span class="entity-name">{{ e.canonical_surface }}</span>
          <span class="label-badge" :style="{ background: nerLabelColor(e.label) }">{{ e.label }}</span>
        </div>
        <div class="entity-stats">
          <span>{{ e.paper_hits.toLocaleString() }} papers</span>
          <span v-if="e.years_active > 0">{{ e.years_active }}y active</span>
        </div>
      </router-link>
    </div>

    <div v-if="hasMore && !loading" class="load-more">
      <button class="btn btn-ghost" @click="loadMore">Load more</button>
    </div>
    <div v-if="loading && entities.length > 0" class="status">
      <span class="spinner"></span> Loading...
    </div>
  </AppShell>
</template>

<style scoped>
.controls {
  margin-bottom: var(--space-5);
}

.label-filter {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.label-chip {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full, 999px);
  font-size: var(--text-xs);
  font-weight: 500;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  text-transform: capitalize;
}
.label-chip:hover {
  border-color: var(--accent);
}
.label-chip.active {
  border-color: transparent;
  background: var(--accent);
  color: #fff;
}

.entity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}

.entity-card {
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.entity-card:hover { text-decoration: none; }

.entity-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-2);
}

.entity-name {
  font-weight: 500;
  font-size: var(--text-base);
  color: var(--text);
  line-height: var(--leading-tight);
}

.label-badge {
  flex-shrink: 0;
  padding: 2px var(--space-2);
  border-radius: var(--radius-full, 999px);
  font-size: var(--text-xs);
  font-weight: 600;
  color: #fff;
  text-transform: capitalize;
  white-space: nowrap;
}

.entity-stats {
  display: flex;
  gap: var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-muted);
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
