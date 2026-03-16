<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppShell from '@/components/AppShell.vue'
import { ApiError, api } from '@/api/client'
import type { BundleListItem } from '@/api/concepts'
import { nerLabelColor } from '@/features/ner/presentation'

const bundles = ref<BundleListItem[]>([])
const loading = ref(true)
const error = ref('')
const hasMore = ref(true)
const limit = 50
const offset = ref(0)

function growthIcon(indicator: BundleListItem['growth_indicator']): string {
  if (indicator === 'growing') return '↗'
  if (indicator === 'declining') return '↘'
  return '→'
}

async function loadBundles() {
  try {
    loading.value = true
    const batch = await api.listBundles(limit, offset.value)
    bundles.value.push(...batch)
    hasMore.value = batch.length === limit
    offset.value += batch.length
  } catch (cause: unknown) {
    error.value = cause instanceof ApiError || cause instanceof Error
      ? cause.message
      : 'Failed to load bundles'
    hasMore.value = false
  } finally {
    loading.value = false
  }
}

function loadMore() {
  if (!loading.value && hasMore.value) {
    void loadBundles()
  }
}

onMounted(() => {
  void loadBundles()
})
</script>

<template>
  <AppShell title="Concept Bundles" :show-search="true">
    <template #actions>
      <span v-if="!loading" class="count">{{ bundles.length }} clusters</span>
    </template>

    <div v-if="loading && bundles.length === 0" class="status"><span class="spinner"></span> Loading bundles...</div>
    <p v-if="error" class="status error">{{ error }}</p>

    <div class="bundle-grid">
      <router-link
        v-for="b in bundles"
        :key="b.bundle_index"
        :to="`/concepts/${b.bundle_index}`"
        class="bundle-card card card-hoverable"
      >
        <div class="bundle-header">
          <span class="bundle-title">Cluster {{ b.bundle_index }}</span>
          <span class="growth-badge" :class="b.growth_indicator">{{ growthIcon(b.growth_indicator) }}</span>
        </div>

        <div class="bundle-entities">
          <span
            v-for="(e, i) in b.top_entities.slice(0, 5)"
            :key="i"
            class="entity-chip"
            :style="{ borderColor: nerLabelColor(e.label) }"
          >{{ e.canonical_surface }}</span>
        </div>

        <div class="bundle-meta">
          <span>{{ b.size }} entities</span>
          <span v-if="b.venue_coverage.length">{{ b.venue_coverage.map((v: string) => v.toUpperCase()).join(' · ') }}</span>
        </div>
      </router-link>
    </div>

    <div v-if="hasMore && !loading" class="load-more">
      <button class="btn btn-ghost" @click="loadMore">Load more</button>
    </div>
    <div v-if="loading && bundles.length > 0" class="status">
      <span class="spinner"></span> Loading...
    </div>
  </AppShell>
</template>

<style scoped>
.bundle-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

.bundle-card {
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.bundle-card:hover { text-decoration: none; }

.bundle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.bundle-title {
  font-weight: 600;
  font-size: var(--text-base);
  color: var(--text);
}
.growth-badge {
  font-size: var(--text-lg);
  font-weight: 700;
}
.growth-badge.growing {
  color: #22c55e;
}
.growth-badge.declining {
  color: #ef4444;
}
.growth-badge.stable {
  color: var(--text-muted);
}

.bundle-entities {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
.entity-chip {
  padding: 2px var(--space-2);
  border-radius: var(--radius-full, 999px);
  font-size: var(--text-xs);
  border: 1.5px solid;
  background: var(--surface);
  color: var(--text);
}

.bundle-meta {
  display: flex;
  gap: var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-muted);
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

.load-more {
  text-align: center;
  padding: var(--space-6);
}
</style>
