<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import { ApiError, api } from '@/api/client'
import type { BundleDetail } from '@/api/concepts'
import { nerLabelColor, parseNodeKey } from '@/features/ner/presentation'

const route = useRoute()
const bundleIndex = computed(() => parseInt(route.params.index as string, 10))

const bundle = ref<BundleDetail | null>(null)
const loading = ref(true)
const error = ref('')

const yearlyData = computed(() => {
  if (!bundle.value?.yearly_paper_counts) return []
  const counts = bundle.value.yearly_paper_counts
  return Object.entries(counts)
    .sort(([a], [b]) => parseInt(a) - parseInt(b))
    .map(([year, count]) => ({ year, count: Number(count) }))
})

const maxCount = computed(() => {
  if (!yearlyData.value.length) return 1
  return Math.max(...yearlyData.value.map((d) => d.count))
})

async function loadBundle() {
  if (!Number.isFinite(bundleIndex.value) || bundleIndex.value <= 0) {
    bundle.value = null
    error.value = 'Invalid bundle id'
    loading.value = false
    return
  }

  try {
    loading.value = true
    error.value = ''
    bundle.value = await api.getBundle(bundleIndex.value)
  } catch (cause: unknown) {
    error.value = cause instanceof ApiError || cause instanceof Error
      ? cause.message
      : 'Bundle not found'
  } finally {
    loading.value = false
  }
}

function memberCanonicalId(nodeKey: string): string {
  return parseNodeKey(nodeKey)?.canonicalId ?? nodeKey
}

function memberLabel(nodeKey: string): string {
  return parseNodeKey(nodeKey)?.label ?? ''
}

onMounted(() => {
  void loadBundle()
})
watch(bundleIndex, () => {
  void loadBundle()
})
</script>

<template>
  <AppShell
    :title="`Cluster ${bundleIndex}`"
    :back-to="'/concepts'"
    :back-label="'Concepts'"
    :show-search="true"
  >
    <div v-if="loading" class="status"><span class="spinner"></span> Loading...</div>
    <p v-else-if="error" class="status error">{{ error }}</p>

    <template v-if="bundle">
      <!-- Stats header -->
      <div class="stat-row">
        <div class="stat-card">
          <span class="stat-value">{{ bundle.size }}</span>
          <span class="stat-label">Entities</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ bundle.venue_count }}</span>
          <span class="stat-label">Venues</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{{ bundle.venue_coverage.map(v => v.toUpperCase()).join(' · ') }}</span>
          <span class="stat-label">Coverage</span>
        </div>
      </div>

      <!-- Top entities -->
      <h3 class="section-title">Top Entities</h3>
      <div class="top-entities">
        <component
          :is="e.canonical_id ? 'router-link' : 'div'"
          v-for="(e, i) in bundle.top_entities"
          :key="i"
          class="entity-row card"
          :class="{ 'card-hoverable': Boolean(e.canonical_id), 'entity-row-static': !e.canonical_id }"
          v-bind="e.canonical_id ? { to: `/entities/${e.canonical_id}` } : {}"
        >
          <span class="entity-name">{{ e.canonical_surface }}</span>
          <span class="label-badge" :style="{ background: nerLabelColor(e.label) }">{{ e.label }}</span>
          <span class="entity-papers">{{ (e.paper_hits || 0).toLocaleString() }} papers</span>
        </component>
      </div>

      <!-- Yearly paper counts bar chart -->
      <h3 class="section-title">Growth Trajectory</h3>
      <div class="bar-chart">
        <div v-for="d in yearlyData" :key="d.year" class="bar-row">
          <span class="bar-label">{{ d.year }}</span>
          <div class="bar-track">
            <div
              class="bar-fill"
              :style="{ width: (d.count / maxCount * 100) + '%' }"
            ></div>
          </div>
          <span class="bar-value">{{ d.count.toLocaleString() }}</span>
        </div>
      </div>

      <!-- All members -->
      <h3 class="section-title">All Members ({{ bundle.members.length }})</h3>
      <div class="members-grid">
        <span
          v-for="m in bundle.members"
          :key="m"
          class="member-chip"
          :style="{ borderColor: nerLabelColor(memberLabel(m)) }"
        >{{ memberCanonicalId(m) }}</span>
      </div>
    </template>
  </AppShell>
</template>

<style scoped>
.stat-row {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-bottom: var(--space-6);
}
.stat-card {
  flex: 1;
  min-width: 120px;
  padding: var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
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

.section-title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
  margin-top: var(--space-6);
}

.top-entities {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.entity-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  text-decoration: none;
  color: inherit;
}
.entity-row:hover { text-decoration: none; }
.entity-row-static {
  cursor: default;
}
.entity-name {
  font-weight: 500;
  flex: 1;
}
.label-badge {
  padding: 2px var(--space-2);
  border-radius: var(--radius-full, 999px);
  font-size: var(--text-xs);
  font-weight: 600;
  color: #fff;
  text-transform: capitalize;
}
.entity-papers {
  font-size: var(--text-sm);
  color: var(--text-muted);
  white-space: nowrap;
}

.bar-chart {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.bar-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.bar-label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  width: 3rem;
  text-align: right;
}
.bar-track {
  flex: 1;
  height: 20px;
  background: var(--surface);
  border-radius: var(--radius);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-hover, var(--accent)));
  border-radius: var(--radius);
  transition: width var(--duration-normal) var(--ease-out);
  min-width: 2px;
}
.bar-value {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  width: 3rem;
}

.members-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.member-chip {
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full, 999px);
  font-size: var(--text-xs);
  border: 1.5px solid;
  background: var(--surface);
  color: var(--text);
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
