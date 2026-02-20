<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type GraphNode, type GraphData, ApiError } from '@/api/client'
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

    <!-- Legend -->
    <div class="legend">
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

    <!-- Canvas -->
    <div class="canvas-container">
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

    <!-- Hover tooltip -->
    <div
      v-if="graph.hoveredNode.value && !graph.selectedNode.value"
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

    <!-- Keyboard hints -->
    <div class="keyboard-hints">
      <kbd>Esc</kbd> Deselect
      <kbd>R</kbd> Reset
      <kbd>+</kbd><kbd>−</kbd> Zoom
      <span class="hint-text">Drag to pan · Scroll to zoom · Double-click to re-center</span>
    </div>
  </div>
</template>

<style scoped>
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
}
</style>
