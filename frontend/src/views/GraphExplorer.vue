<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type GraphNode, type GraphData, type AggregateEntry, ApiError } from '@/api/client'
import { useForceGraph } from '@/composables/useForceGraph'

const route = useRoute()
const router = useRouter()
const entryId = route.params.id as string

// Graph engine
const graph = useForceGraph()
const canvasRef = ref<HTMLCanvasElement | null>(null)

// UI state
const loading = ref(true)
const error = ref('')
const depth = ref(1)
const maxNodes = ref(80)
const showPanel = ref(true)
const graphData = ref<GraphData | null>(null)
const activeTab = ref<'graph' | 'prior' | 'derivative'>('graph')

// Filter state
const filterKeyword = ref('')
const yearMin = ref(1990)
const yearMax = ref(2026)
const filterYearMin = ref(1990)
const filterYearMax = ref(2026)

// Computed: year histogram + bounds
const yearHistogram = computed(() => {
  if (!graphData.value) return []
  const counts: Record<number, number> = {}
  for (const n of graphData.value.nodes) {
    if (n.year) counts[n.year] = (counts[n.year] || 0) + 1
  }
  const result: { year: number; count: number }[] = []
  for (let y = yearMin.value; y <= yearMax.value; y++) {
    result.push({ year: y, count: counts[y] || 0 })
  }
  return result
})

const maxHistCount = computed(() => Math.max(1, ...yearHistogram.value.map(h => h.count)))

// Fetch graph data
const fetchGraph = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await api.getGraph(entryId, depth.value, maxNodes.value)
    graphData.value = data
    if (data.nodes.length === 0) {
      error.value = 'No citation data available yet. Visit the entry page first to trigger S2 sync.'
      return
    }
    // Set year bounds
    const years = data.nodes.map(n => n.year).filter(Boolean) as number[]
    if (years.length > 0) {
      yearMin.value = Math.min(...years)
      yearMax.value = Math.max(...years)
      filterYearMin.value = yearMin.value
      filterYearMax.value = yearMax.value
    }
    graph.loadData(data)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      error.value = 'No Semantic Scholar data for this entry yet. Open the entry detail page to trigger a sync.'
    } else {
      error.value = 'Failed to load graph data.'
      console.error(e)
    }
  } finally {
    loading.value = false
  }
}

// Initialize canvas
onMounted(() => {
  if (canvasRef.value) {
    graph.init(canvasRef.value)
  }
  fetchGraph()

  // Keyboard shortcuts
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

// Re-fetch on depth/maxNodes change
watch(depth, fetchGraph)
watch(maxNodes, () => {
  // Debounce slider
  const val = maxNodes.value
  setTimeout(() => {
    if (maxNodes.value === val) fetchGraph()
  }, 300)
})

// Node click: select and show panel
graph.onNodeClick((_node: GraphNode) => {
  showPanel.value = true
})

// Node double-click: re-center on that node if in library
graph.onNodeDblClick((node: GraphNode) => {
  if (node.in_library && node.entry_id) {
    router.push({ name: 'graph', params: { id: node.entry_id } })
  }
})

// Keyboard
function onKeydown(e: KeyboardEvent) {
  if (e.target instanceof HTMLInputElement) return

  switch (e.key) {
    case 'Escape':
      graph.selectedNode.value = null
      showPanel.value = false
      break
    case 'r':
    case 'R':
      graph.resetView()
      break
    case '+':
    case '=':
      graph.zoomIn()
      break
    case '-':
      graph.zoomOut()
      break
  }
}

// Navigate to entry
function goToEntry(id: string) {
  router.push({ name: 'entry', params: { id } })
}

// Open on S2
function openOnS2(s2Id: string) {
  window.open(`https://www.semanticscholar.org/paper/${s2Id}`, '_blank')
}

// Re-center graph on a different entry
function recenterOn(node: GraphNode) {
  if (node.in_library && node.entry_id) {
    router.push({ name: 'graph', params: { id: node.entry_id } })
  }
}

// Format authors
function formatAuthors(authors: string[]): string {
  if (authors.length <= 3) return authors.join(', ')
  return authors.slice(0, 3).join(', ') + ` +${authors.length - 3}`
}
// Format citation count
function fmtCount(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toString()
}

// Apply filters
function applyFilter() {
  const kw = filterKeyword.value.trim().toLowerCase()
  const yMin = filterYearMin.value
  const yMax = filterYearMax.value

  // No filter active?
  const noYearFilter = yMin <= yearMin.value && yMax >= yearMax.value
  const noKeywordFilter = kw === ''

  if (noYearFilter && noKeywordFilter) {
    graph.setFilter(null)
    return
  }

  graph.setFilter((node) => {
    // Year filter
    if (node.year && (node.year < yMin || node.year > yMax)) return false
    // Keyword filter
    if (kw) {
      const text = [node.title, ...node.authors, node.venue || ''].join(' ').toLowerCase()
      if (!text.includes(kw)) return false
    }
    return true
  })
}

// Watch filter changes
watch([filterYearMin, filterYearMax], applyFilter)
watch(filterKeyword, () => {
  // Debounce keyword
  const val = filterKeyword.value
  setTimeout(() => {
    if (filterKeyword.value === val) applyFilter()
  }, 200)
})
</script>

<template>
  <div class="graph-page" :class="{ 'panel-open': showPanel && graph.selectedNode.value }">
    <!-- Top toolbar -->
    <header class="toolbar">
      <div class="toolbar-left">
        <router-link to="/" class="brand">Folio</router-link>
        <button class="back-btn" @click="router.back()">← Back</button>
        <span class="divider">|</span>
        <span class="toolbar-title">Citation Graph</span>
      </div>

      <div class="toolbar-controls">
        <div class="control-group">
          <label class="control-label">Depth</label>
          <div class="toggle-group">
            <button
              :class="['toggle-btn', { active: depth === 1 }]"
              @click="depth = 1"
            >1-hop</button>
            <button
              :class="['toggle-btn', { active: depth === 2 }]"
              @click="depth = 2"
            >2-hop</button>
          </div>
        </div>

        <div class="control-group">
          <label class="control-label">View</label>
          <div class="toggle-group">
            <button
              :class="['toggle-btn', { active: graph.viewMode.value === 'citation' }]"
              @click="graph.setViewMode('citation')"
            >Citation</button>
            <button
              :class="['toggle-btn', { active: graph.viewMode.value === 'similarity' }]"
              @click="graph.setViewMode('similarity')"
            >Similarity</button>
          </div>
        </div>

        <div class="control-group">
          <label class="control-label">Nodes: {{ maxNodes }}</label>
          <input
            type="range"
            v-model.number="maxNodes"
            min="20"
            max="150"
            step="10"
            class="range-slider"
          />
        </div>

        <button class="icon-btn" @click="graph.resetView()" title="Reset view (R)">⟳</button>
        <button class="icon-btn" @click="graph.zoomIn()" title="Zoom in (+)">+</button>
        <button class="icon-btn" @click="graph.zoomOut()" title="Zoom out (-)">−</button>
      </div>
    </header>

    <!-- Tabs: Graph | Prior Works | Derivative Works -->
    <nav class="view-tabs">
      <button
        :class="['view-tab', { active: activeTab === 'graph' }]"
        @click="activeTab = 'graph'"
      >◉ Graph</button>
      <button
        :class="['view-tab', { active: activeTab === 'prior' }]"
        @click="activeTab = 'prior'"
      >
        Prior Works
        <span v-if="graphData?.prior_works?.length" class="tab-count">{{ graphData.prior_works.length }}</span>
      </button>
      <button
        :class="['view-tab', { active: activeTab === 'derivative' }]"
        @click="activeTab = 'derivative'"
      >
        Derivative Works
        <span v-if="graphData?.derivative_works?.length" class="tab-count">{{ graphData.derivative_works.length }}</span>
      </button>
    </nav>

    <!-- Filter bar (graph tab only) -->
    <div v-if="activeTab === 'graph' && graphData" class="filter-bar">
      <div class="filter-group filter-year">
        <label class="filter-label">Year: {{ filterYearMin }}–{{ filterYearMax }}</label>
        <div class="year-slider-container">
          <!-- Histogram sparkline -->
          <div class="year-histogram">
            <div
              v-for="h in yearHistogram"
              :key="h.year"
              class="hist-bar"
              :style="{
                height: (h.count / maxHistCount) * 100 + '%',
                opacity: h.year >= filterYearMin && h.year <= filterYearMax ? 1 : 0.2
              }"
              :title="`${h.year}: ${h.count} papers`"
            ></div>
          </div>
          <!-- Dual range sliders (layered) -->
          <div class="dual-range">
            <input
              type="range"
              :min="yearMin"
              :max="yearMax"
              v-model.number="filterYearMin"
              class="range-min"
            />
            <input
              type="range"
              :min="yearMin"
              :max="yearMax"
              v-model.number="filterYearMax"
              class="range-max"
            />
          </div>
        </div>
      </div>

      <div class="filter-group filter-keyword">
        <input
          type="text"
          v-model="filterKeyword"
          placeholder="Filter by keyword…"
          class="keyword-input"
        />
      </div>
    </div>

    <!-- Legend (graph tab only) -->
    <div v-if="activeTab === 'graph'" class="legend">
      <div class="legend-item">
        <span class="legend-swatch swatch-cool"></span>
        <span>Older</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch swatch-warm"></span>
        <span>Newer</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch swatch-library"></span>
        <span>In Library</span>
      </div>
      <div class="legend-item">
        <span class="legend-swatch swatch-size-sm"></span>
        <span class="legend-swatch swatch-size-lg"></span>
        <span>Citations</span>
      </div>
    </div>

    <!-- Canvas (graph tab) -->
    <div v-show="activeTab === 'graph'" class="canvas-container">
      <div v-if="loading" class="overlay-message">
        <div class="spinner"></div>
        <p>Loading citation graph…</p>
      </div>
      <div v-else-if="error" class="overlay-message">
        <p class="error-text">{{ error }}</p>
        <router-link :to="{ name: 'entry', params: { id: entryId } }" class="action-link">
          ← Go to entry detail
        </router-link>
      </div>
      <canvas ref="canvasRef" class="graph-canvas"></canvas>
    </div>

    <!-- Prior Works table -->
    <div v-if="activeTab === 'prior'" class="aggregate-container">
      <div class="aggregate-header">
        <h2 class="aggregate-title">Prior Works</h2>
        <p class="aggregate-desc">Papers most frequently cited by the papers in this graph — the intellectual foundations of this research area.</p>
      </div>
      <div v-if="!graphData?.prior_works?.length" class="aggregate-empty">
        No prior works found. This may happen if citation data is still syncing.
      </div>
      <table v-else class="aggregate-table">
        <thead>
          <tr>
            <th class="th-title">Paper</th>
            <th class="th-num">Year</th>
            <th class="th-num">Citations</th>
            <th class="th-num">Freq</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="paper in graphData.prior_works"
            :key="paper.id"
            class="agg-row"
            :class="{ 'in-library': paper.in_library }"
            @click="paper.entry_id ? goToEntry(paper.entry_id) : openOnS2(paper.id)"
          >
            <td class="td-title">
              <div class="agg-paper-title">{{ paper.title }}</div>
              <div class="agg-paper-authors">{{ formatAuthors(paper.authors) }}</div>
              <div v-if="paper.venue" class="agg-paper-venue">{{ paper.venue }}</div>
            </td>
            <td class="td-num">{{ paper.year || '—' }}</td>
            <td class="td-num">{{ fmtCount(paper.citation_count) }}</td>
            <td class="td-num">
              <span class="freq-badge">{{ paper.frequency }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Derivative Works table -->
    <div v-if="activeTab === 'derivative'" class="aggregate-container">
      <div class="aggregate-header">
        <h2 class="aggregate-title">Derivative Works</h2>
        <p class="aggregate-desc">Papers that cite many papers in this graph — recent surveys and state-of-the-art developments.</p>
      </div>
      <div v-if="!graphData?.derivative_works?.length" class="aggregate-empty">
        No derivative works found. This may happen if citation data is still syncing.
      </div>
      <table v-else class="aggregate-table">
        <thead>
          <tr>
            <th class="th-title">Paper</th>
            <th class="th-num">Year</th>
            <th class="th-num">Citations</th>
            <th class="th-num">Freq</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="paper in graphData.derivative_works"
            :key="paper.id"
            class="agg-row"
            :class="{ 'in-library': paper.in_library }"
            @click="paper.entry_id ? goToEntry(paper.entry_id) : openOnS2(paper.id)"
          >
            <td class="td-title">
              <div class="agg-paper-title">{{ paper.title }}</div>
              <div class="agg-paper-authors">{{ formatAuthors(paper.authors) }}</div>
              <div v-if="paper.venue" class="agg-paper-venue">{{ paper.venue }}</div>
            </td>
            <td class="td-num">{{ paper.year || '—' }}</td>
            <td class="td-num">{{ fmtCount(paper.citation_count) }}</td>
            <td class="td-num">
              <span class="freq-badge">{{ paper.frequency }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Hover tooltip (graph tab only) -->
    <div
      v-if="activeTab === 'graph' && graph.hoveredNode.value && !graph.selectedNode.value"
      class="tooltip"
    >
      <div class="tooltip-title">{{ graph.hoveredNode.value.title }}</div>
      <div class="tooltip-meta">
        <span v-if="graph.hoveredNode.value.venue">{{ graph.hoveredNode.value.venue }}</span>
        <span v-if="graph.hoveredNode.value.year">{{ graph.hoveredNode.value.year }}</span>
        <span>{{ graph.hoveredNode.value.citation_count }} citations</span>
      </div>
      <div v-if="graph.hoveredNode.value.in_library" class="tooltip-badge">📚 In your library</div>
    </div>

    <!-- Side panel -->
    <aside
      v-if="showPanel && graph.selectedNode.value"
      class="detail-panel"
    >
      <div class="panel-header">
        <h3 class="panel-title">Paper Details</h3>
        <button class="close-btn" @click="showPanel = false; graph.selectedNode.value = null">✕</button>
      </div>

      <div class="panel-content">
        <h2 class="paper-title">{{ graph.selectedNode.value.title }}</h2>

        <p class="paper-authors">{{ formatAuthors(graph.selectedNode.value.authors) }}</p>

        <div class="paper-meta">
          <span v-if="graph.selectedNode.value.venue" class="meta-tag">{{ graph.selectedNode.value.venue }}</span>
          <span v-if="graph.selectedNode.value.year" class="meta-tag">{{ graph.selectedNode.value.year }}</span>
          <span class="meta-tag">{{ graph.selectedNode.value.citation_count.toLocaleString() }} citations</span>
        </div>

        <div v-if="graph.selectedNode.value.fields_of_study?.length" class="fields">
          <span
            v-for="field in graph.selectedNode.value.fields_of_study"
            :key="field"
            class="field-tag"
          >{{ field }}</span>
        </div>

        <div class="panel-actions">
          <button
            v-if="graph.selectedNode.value.in_library && graph.selectedNode.value.entry_id"
            class="action-btn primary"
            @click="goToEntry(graph.selectedNode.value!.entry_id!)"
          >View in Folio</button>

          <button
            v-if="graph.selectedNode.value.in_library && graph.selectedNode.value.entry_id"
            class="action-btn"
            @click="recenterOn(graph.selectedNode.value!)"
          >Re-center Graph</button>

          <button
            class="action-btn"
            @click="openOnS2(graph.selectedNode.value!.id)"
          >Open on Semantic Scholar ↗</button>
        </div>

        <div v-if="graph.selectedNode.value.in_library" class="library-badge">
          <span class="badge-icon">📚</span>
          <span>This paper is in your library</span>
        </div>
      </div>
    </aside>

    <!-- Keyboard hints (graph tab only) -->
    <div v-if="activeTab === 'graph'" class="keyboard-hints">
      <kbd>Esc</kbd> Deselect
      <kbd>R</kbd> Reset
      <kbd>+</kbd><kbd>−</kbd> Zoom
      <span class="hint-text">Drag to pan · Scroll to zoom · Double-click to re-center</span>
    </div>
  </div>
</template>

<style scoped>
/* ── View Tabs ── */
.view-tabs {
  display: flex;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 0 var(--space-4);
}

/* ── Filter Bar ── */
.filter-bar {
  display: flex;
  align-items: flex-end;
  gap: var(--space-6);
  padding: var(--space-2) var(--space-4);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.filter-label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-weight: 600;
}

.filter-year {
  flex: 1;
  max-width: 400px;
}

.year-slider-container {
  position: relative;
  height: 50px;
}

.year-histogram {
  display: flex;
  align-items: flex-end;
  height: 28px;
  gap: 1px;
  padding-bottom: 2px;
}

.hist-bar {
  flex: 1;
  min-width: 2px;
  background: var(--accent);
  border-radius: 1px 1px 0 0;
  transition: opacity 0.15s;
  min-height: 1px;
}

.dual-range {
  position: relative;
  height: 20px;
}

.dual-range input[type="range"] {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  pointer-events: none;
  -webkit-appearance: none;
  appearance: none;
  background: transparent;
  height: 20px;
  margin: 0;
}

.dual-range input[type="range"]::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--bg-surface);
  cursor: pointer;
  pointer-events: auto;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.dual-range input[type="range"]::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  border: 2px solid var(--bg-surface);
  cursor: pointer;
  pointer-events: auto;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.dual-range input[type="range"]::-webkit-slider-runnable-track {
  height: 3px;
  background: var(--border);
  border-radius: 2px;
}

.dual-range input[type="range"]::-moz-range-track {
  height: 3px;
  background: var(--border);
  border-radius: 2px;
}

.filter-keyword {
  min-width: 180px;
}

.keyword-input {
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
  font-size: var(--text-sm);
  width: 100%;
  outline: none;
  transition: border-color 0.15s;
}

.keyword-input:focus {
  border-color: var(--accent);
}

.view-tab {
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}

.view-tab:hover {
  color: var(--text);
}

.view-tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--border);
  border-radius: 9px;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
}

.view-tab.active .tab-count {
  background: var(--accent);
  color: white;
}

/* ── Layout ── */
.graph-page {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg);
  overflow: hidden;
}

.canvas-container {
  flex: 1;
  position: relative;
}

.graph-canvas {
  width: 100%;
  height: 100%;
  display: block;
  cursor: grab;
}

/* ── Toolbar ── */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-4);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  z-index: 10;
  gap: var(--space-4);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.brand {
  font-weight: 600;
  font-size: var(--text-lg);
  color: var(--text);
  text-decoration: none;
}

.back-btn {
  color: var(--text-muted);
  font-size: var(--text-sm);
  cursor: pointer;
}
.back-btn:hover { color: var(--text); }

.divider {
  color: var(--border);
}

.toolbar-title {
  font-weight: 500;
  color: var(--text);
}

.toolbar-controls {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.control-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.control-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
  white-space: nowrap;
}

.toggle-group {
  display: flex;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.toggle-btn {
  padding: 4px 12px;
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--bg);
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
}

.toggle-btn.active {
  background: var(--accent);
  color: white;
}

.range-slider {
  width: 100px;
  accent-color: var(--accent);
}

.icon-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: var(--bg);
  cursor: pointer;
  font-size: 16px;
  transition: all 0.15s ease;
}
.icon-btn:hover {
  color: var(--text);
  border-color: var(--text-muted);
}

/* ── Legend ── */
.legend {
  position: absolute;
  bottom: 50px;
  left: var(--space-4);
  display: flex;
  gap: var(--space-4);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: var(--text-sm);
  color: var(--text-muted);
  z-index: 5;
  opacity: 0.9;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.swatch-cool { background: hsl(220, 55%, 50%); }
.swatch-warm { background: hsl(30, 55%, 50%); }
.swatch-library {
  background: transparent;
  border: 2.5px solid var(--accent);
}
.swatch-size-sm { width: 6px; height: 6px; background: var(--text-muted); }
.swatch-size-lg { width: 14px; height: 14px; background: var(--text-muted); }

/* ── Overlay messages ── */
.overlay-message {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  z-index: 5;
  background: var(--bg);
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-text {
  color: var(--text-muted);
  text-align: center;
  max-width: 400px;
}

.action-link {
  color: var(--accent);
  font-size: var(--text-sm);
}

/* ── Tooltip ── */
.tooltip {
  position: fixed;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 15;
  max-width: 500px;
  pointer-events: none;
}

.tooltip-title {
  font-weight: 600;
  font-size: var(--text-sm);
  margin-bottom: 4px;
  line-height: 1.3;
}

.tooltip-meta {
  display: flex;
  gap: var(--space-2);
  font-size: 0.8rem;
  color: var(--text-muted);
}

.tooltip-badge {
  margin-top: 4px;
  font-size: 0.8rem;
  color: var(--accent);
}

/* ── Detail Panel ── */
.detail-panel {
  position: fixed;
  right: 0;
  top: 0;
  bottom: 0;
  width: 380px;
  background: var(--bg-surface);
  border-left: 1px solid var(--border);
  z-index: 20;
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.1);
  animation: slideIn 0.2s ease;
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
}

.panel-title {
  font-size: var(--text-sm);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.close-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s;
}
.close-btn:hover {
  background: var(--border);
  color: var(--text);
}

.panel-content {
  flex: 1;
  padding: var(--space-4);
  overflow-y: auto;
}

.paper-title {
  font-size: var(--text-lg);
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: var(--space-2);
}

.paper-authors {
  color: var(--text-muted);
  font-size: var(--text-sm);
  margin-bottom: var(--space-3);
}

.paper-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.meta-tag {
  padding: 2px 8px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.fields {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-bottom: var(--space-4);
}

.field-tag {
  padding: 2px 8px;
  background: var(--accent);
  color: white;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  opacity: 0.85;
}

.panel-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.action-btn {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: var(--text-sm);
  color: var(--text);
  background: var(--bg);
  cursor: pointer;
  text-align: center;
  transition: all 0.15s;
}

.action-btn:hover {
  border-color: var(--text-muted);
}

.action-btn.primary {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.action-btn.primary:hover {
  opacity: 0.9;
}

.library-badge {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg);
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  font-size: var(--text-sm);
  color: var(--accent);
}

.badge-icon {
  font-size: 1.2em;
}

/* ── Keyboard hints ── */
.keyboard-hints {
  position: absolute;
  bottom: var(--space-3);
  right: var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 0.75rem;
  color: var(--text-muted);
  opacity: 0.6;
  z-index: 5;
}

.keyboard-hints kbd {
  padding: 1px 5px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: 3px;
  font-family: inherit;
  font-size: 0.7rem;
}

.hint-text {
  margin-left: var(--space-2);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .detail-panel {
    width: 100%;
  }

  .toolbar-controls {
    gap: var(--space-2);
  }

  .range-slider {
    display: none;
  }

  .legend {
    display: none;
  }

  .keyboard-hints {
    display: none;
  }

  .aggregate-table .th-num,
  .aggregate-table .td-num {
    display: none;
  }

  .aggregate-table .th-num:last-child,
  .aggregate-table .td-num:last-child {
    display: table-cell;
  }
}

/* ── Aggregate Tables ── */
.aggregate-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-8);
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}

.aggregate-header {
  margin-bottom: var(--space-6);
}

.aggregate-title {
  font-size: var(--text-xl);
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.aggregate-desc {
  color: var(--text-muted);
  font-size: var(--text-sm);
  line-height: 1.5;
}

.aggregate-empty {
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-8);
}

.aggregate-table {
  width: 100%;
  border-collapse: collapse;
}

.aggregate-table thead {
  position: sticky;
  top: 0;
  z-index: 2;
}

.aggregate-table th {
  padding: var(--space-2) var(--space-3);
  text-align: left;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  background: var(--bg);
  border-bottom: 2px solid var(--border);
}

.th-num {
  text-align: right !important;
  width: 80px;
}

.agg-row {
  cursor: pointer;
  transition: background 0.1s;
}

.agg-row:hover {
  background: var(--bg-surface);
}

.agg-row.in-library {
  border-left: 3px solid var(--accent);
}

.agg-row td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}

.td-num {
  text-align: right;
  font-size: var(--text-sm);
  color: var(--text-muted);
  white-space: nowrap;
}

.agg-paper-title {
  font-weight: 500;
  font-size: var(--text-sm);
  line-height: 1.4;
  margin-bottom: 2px;
}

.agg-paper-authors {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.agg-paper-venue {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 2px;
  opacity: 0.7;
}

.freq-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 22px;
  padding: 0 6px;
  background: var(--accent);
  color: white;
  border-radius: 11px;
  font-size: 0.75rem;
  font-weight: 600;
}
</style>
