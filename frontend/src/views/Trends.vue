<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import AppShell from '@/components/AppShell.vue'
import { ApiError, api } from '@/api/client'
import type { TrendMoverItem, EmergenceItem, CrossVenueFlowItem, TrendsDashboardStats } from '@/api/trends'
import { nerLabelColor } from '@/features/ner/presentation'

const activeTab = ref<'movers' | 'emergence' | 'flow'>('movers')
const stats = ref<TrendsDashboardStats | null>(null)
const movers = ref<TrendMoverItem[]>([])
const emergence = ref<EmergenceItem[]>([])
const flow = ref<CrossVenueFlowItem[]>([])
const loading = ref(true)
const error = ref('')

// Filters
const selectedLabel = ref('')
const selectedVenue = ref('')
const selectedDirection = ref('')

function setLoadError(cause: unknown, fallback: string) {
  error.value = cause instanceof ApiError || cause instanceof Error
    ? cause.message
    : fallback
}

function momentumArrow(dir: TrendMoverItem['change_direction']): string {
  if (dir === 'rising') return '↑'
  if (dir === 'falling') return '↓'
  return '→'
}

function momentumClass(dir: TrendMoverItem['change_direction']): string {
  if (dir === 'rising') return 'rising'
  if (dir === 'falling') return 'falling'
  return 'stable'
}

async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    stats.value = await api.getTrendsStats()
    await Promise.all([loadMovers(), loadEmergence()])
  } catch (cause: unknown) {
    setLoadError(cause, 'Failed to load trends')
  } finally {
    loading.value = false
  }
}

async function loadMovers() {
  const params: Parameters<typeof api.getMovers>[0] = { limit: 100 }
  if (selectedLabel.value) params.label = selectedLabel.value
  if (selectedVenue.value) params.venue = selectedVenue.value
  if (selectedDirection.value) params.direction = selectedDirection.value
  try {
    movers.value = await api.getMovers(params)
    error.value = ''
  } catch (cause: unknown) {
    movers.value = []
    setLoadError(cause, 'Failed to load movers')
  }
}

async function loadEmergence() {
  const params: Parameters<typeof api.getEmergence>[0] = { limit: 100 }
  if (selectedLabel.value) params.label = selectedLabel.value
  if (selectedVenue.value) params.venue = selectedVenue.value
  try {
    emergence.value = await api.getEmergence(params)
    error.value = ''
  } catch (cause: unknown) {
    emergence.value = []
    setLoadError(cause, 'Failed to load emergence watchlist')
  }
}

async function loadFlow() {
  const params: Parameters<typeof api.getCrossVenueFlow>[0] = {
    limit: 100,
    min_transfer_score: 0.3,
  }
  if (selectedLabel.value) params.label = selectedLabel.value
  if (selectedVenue.value) params.source_venue = selectedVenue.value
  try {
    flow.value = await api.getCrossVenueFlow(params)
    error.value = ''
  } catch (cause: unknown) {
    flow.value = []
    setLoadError(cause, 'Failed to load cross-venue flow')
  }
}

// Reload when filters change
watch([selectedLabel, selectedVenue, selectedDirection], () => {
  if (loading.value) return
  if (activeTab.value === 'movers') void loadMovers()
  else if (activeTab.value === 'emergence') void loadEmergence()
  else if (activeTab.value === 'flow') void loadFlow()
})

watch(activeTab, (tab) => {
  if (tab === 'flow' && flow.value.length === 0) {
    void loadFlow()
  }
})

onMounted(() => {
  void loadDashboard()
})
</script>

<template>
  <AppShell title="Trends" :show-search="true">
    <template #actions>
      <span v-if="stats" class="stats-badge">
        {{ stats.total_entities.toLocaleString() }} entities ·
        {{ stats.emerging_count }} emerging
      </span>
    </template>

    <!-- Stat header cards -->
    <div v-if="stats" class="stat-row">
      <div class="stat-card">
        <span class="stat-value">{{ stats.total_entities.toLocaleString() }}</span>
        <span class="stat-label">Tracked Entities</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ stats.emerging_count }}</span>
        <span class="stat-label">Emerging</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{{ stats.venues.map(v => v.toUpperCase()).join(' · ') }}</span>
        <span class="stat-label">Venues</span>
      </div>
      <div class="stat-card" v-if="stats.year_range.length === 2">
        <span class="stat-value">{{ stats.year_range[0] }}–{{ stats.year_range[1] }}</span>
        <span class="stat-label">Span</span>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters">
      <select v-model="selectedLabel" class="filter-select">
        <option value="">All labels</option>
        <option v-for="l in stats?.labels || []" :key="l" :value="l">{{ l }}</option>
      </select>
      <select v-model="selectedVenue" class="filter-select">
        <option value="">All venues</option>
        <option v-for="v in stats?.venues || []" :key="v" :value="v">{{ v.toUpperCase() }}</option>
      </select>
      <select v-if="activeTab === 'movers'" v-model="selectedDirection" class="filter-select">
        <option value="">All directions</option>
        <option value="rising">↑ Rising</option>
        <option value="falling">↓ Falling</option>
        <option value="stable">→ Stable</option>
      </select>
    </div>

    <!-- Tabs -->
    <nav class="tabs-nav">
      <div class="segmented">
        <button
          v-for="tab in (['movers', 'emergence', 'flow'] as const)"
          :key="tab"
          :class="['segmented-item', { active: activeTab === tab }]"
          @click="activeTab = tab"
        >{{ tab === 'flow' ? 'cross-venue' : tab }}</button>
      </div>
    </nav>

    <div v-if="loading" class="status"><span class="spinner"></span> Loading trends...</div>
    <p v-else-if="error" class="status error">{{ error }}</p>

    <!-- Movers tab -->
    <section v-if="activeTab === 'movers' && !loading && !error" class="tab-content">
      <div v-if="movers.length === 0" class="empty">No movers data available</div>
      <table v-else class="trends-table">
        <thead>
          <tr>
            <th>Entity</th>
            <th>Label</th>
            <th>Venue</th>
            <th class="num">Papers</th>
            <th class="num">Prevalence</th>
            <th class="num">Momentum</th>
            <th class="num">Direction</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in movers" :key="m.canonical_id + m.venue">
            <td>
              <router-link :to="`/entities/${m.canonical_id}`" class="entity-link">
                {{ m.canonical_surface }}
              </router-link>
              <span v-if="m.change_point" class="change-dot" title="Change point detected">●</span>
            </td>
            <td><span class="label-badge-sm" :style="{ background: nerLabelColor(m.label) }">{{ m.label }}</span></td>
            <td class="venue-cell">{{ m.venue.toUpperCase() }}</td>
            <td class="num">{{ m.paper_hits.toLocaleString() }}</td>
            <td class="num">{{ (m.prevalence * 100).toFixed(1) }}%</td>
            <td class="num">{{ m.momentum >= 0 ? '+' : '' }}{{ (m.momentum * 100).toFixed(2) }}%</td>
            <td class="num"><span :class="['direction', momentumClass(m.change_direction)]">{{ momentumArrow(m.change_direction) }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Emergence tab -->
    <section v-if="activeTab === 'emergence' && !loading && !error" class="tab-content">
      <div v-if="emergence.length === 0" class="empty">No emerging entities</div>
      <table v-else class="trends-table">
        <thead>
          <tr>
            <th>Entity</th>
            <th>Label</th>
            <th>Venue</th>
            <th class="num">Papers</th>
            <th class="num">Emergence</th>
            <th class="num">Momentum</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="e in emergence" :key="e.canonical_id + e.venue">
            <td>
              <router-link :to="`/entities/${e.canonical_id}`" class="entity-link">
                {{ e.canonical_surface }}
              </router-link>
            </td>
            <td><span class="label-badge-sm" :style="{ background: nerLabelColor(e.label) }">{{ e.label }}</span></td>
            <td class="venue-cell">{{ e.venue.toUpperCase() }}</td>
            <td class="num">{{ e.paper_hits.toLocaleString() }}</td>
            <td class="num emergence-score">{{ e.emergence_score.toFixed(3) }}</td>
            <td class="num">{{ e.momentum >= 0 ? '+' : '' }}{{ (e.momentum * 100).toFixed(2) }}%</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Cross-venue flow tab -->
    <section v-if="activeTab === 'flow' && !loading && !error" class="tab-content">
      <div v-if="flow.length === 0" class="empty">No cross-venue flow data</div>
      <table v-else class="trends-table">
        <thead>
          <tr>
            <th>Entity</th>
            <th>Label</th>
            <th>Source</th>
            <th>Target</th>
            <th class="num">Lag</th>
            <th class="num">Transfer</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(f, i) in flow" :key="i">
            <td>
              <router-link :to="`/entities/${f.canonical_id}`" class="entity-link">
                {{ f.canonical_surface }}
              </router-link>
            </td>
            <td><span class="label-badge-sm" :style="{ background: nerLabelColor(f.label) }">{{ f.label }}</span></td>
            <td class="venue-cell">{{ f.source_venue.toUpperCase() }} {{ f.source_year }}</td>
            <td class="venue-cell">{{ f.target_venue.toUpperCase() }} {{ f.target_year }}</td>
            <td class="num">{{ f.lag_years }}y</td>
            <td class="num">{{ f.transfer_score.toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </AppShell>
</template>

<style scoped>
.stats-badge {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.stat-row {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
  margin-bottom: var(--space-5);
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

.filters {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}
.filter-select {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-sm);
  min-width: 130px;
  text-transform: capitalize;
}

.tabs-nav {
  margin-bottom: var(--space-4);
}
.segmented {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.segmented-item {
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  font-weight: 500;
  background: var(--surface);
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  text-transform: capitalize;
}
.segmented-item + .segmented-item {
  border-left: 1px solid var(--border);
}
.segmented-item.active {
  background: var(--accent);
  color: #fff;
}
.segmented-item:hover:not(.active) {
  background: var(--bg-surface);
}

.trends-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}
.trends-table th {
  text-align: left;
  padding: var(--space-2) var(--space-3);
  border-bottom: 2px solid var(--border);
  font-weight: 600;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.trends-table td {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
  color: var(--text);
}
.trends-table th.num,
.trends-table td.num {
  text-align: right;
}
.trends-table tbody tr:hover {
  background: var(--bg-surface);
}

.entity-link {
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
}
.entity-link:hover { text-decoration: underline; }

.label-badge-sm {
  padding: 1px var(--space-2);
  border-radius: var(--radius-full, 999px);
  font-size: var(--text-xs);
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
}

.venue-cell {
  font-weight: 600;
  font-size: var(--text-xs);
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.change-dot {
  color: #ef4444;
  font-size: 8px;
  margin-left: var(--space-1);
  vertical-align: super;
}

.direction {
  font-weight: 700;
  font-size: var(--text-base);
}
.direction.rising { color: #22c55e; }
.direction.falling { color: #ef4444; }
.direction.stable { color: var(--text-muted); }

.emergence-score {
  font-weight: 600;
  color: var(--accent);
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

.empty {
  text-align: center;
  padding: var(--space-8);
  color: var(--text-muted);
}
</style>
