<script setup lang="ts">
import GraphAggregateTable from '@/features/graph/components/GraphAggregateTable.vue'
import GraphDetailPanel from '@/features/graph/components/GraphDetailPanel.vue'
import GraphFilterBar from '@/features/graph/components/GraphFilterBar.vue'
import GraphKeyboardHints from '@/features/graph/components/GraphKeyboardHints.vue'
import GraphLegend from '@/features/graph/components/GraphLegend.vue'
import GraphTabs from '@/features/graph/components/GraphTabs.vue'
import GraphToolbar from '@/features/graph/components/GraphToolbar.vue'
import GraphTooltip from '@/features/graph/components/GraphTooltip.vue'
import '@/features/graph/graphExplorer.css'
import { useGraphExplorer } from '@/composables/useGraphExplorer'

const {
  activeTab,
  canvasRef,
  depth,
  entryId,
  error,
  filterKeyword,
  filterYearMax,
  filterYearMin,
  fmtCount,
  formatAuthors,
  goToEntry,
  graphData,
  hoveredNode,
  maxHistCount,
  maxNodes,
  overlayState,
  openOnS2,
  recenterOn,
  router,
  closePanel,
  selectedNode,
  setViewMode,
  showPanel,
  resetView,
  viewMode,
  yearHistogram,
  yearMax,
  yearMin,
  zoomIn,
  zoomOut,
} = useGraphExplorer()

void canvasRef
</script>

<template>
  <div class="graph-page" :class="{ 'panel-open': showPanel && selectedNode }">
    <GraphToolbar
      :depth="depth"
      :max-nodes="maxNodes"
      :view-mode="viewMode"
      @back="router.back()"
      @reset="resetView()"
      @update:depth="depth = $event"
      @update:max-nodes="maxNodes = $event"
      @update:view-mode="setViewMode($event)"
      @zoom-in="zoomIn()"
      @zoom-out="zoomOut()"
    />

    <GraphTabs
      :active-tab="activeTab"
      :prior-count="graphData?.prior_works.length ?? 0"
      :derivative-count="graphData?.derivative_works.length ?? 0"
      @update:active-tab="activeTab = $event"
    />

    <GraphFilterBar
      v-if="activeTab === 'graph' && graphData"
      :filter-keyword="filterKeyword"
      :filter-year-max="filterYearMax"
      :filter-year-min="filterYearMin"
      :max-hist-count="maxHistCount"
      :year-histogram="yearHistogram"
      :year-max="yearMax"
      :year-min="yearMin"
      @update:filter-keyword="filterKeyword = $event"
      @update:filter-year-max="filterYearMax = $event"
      @update:filter-year-min="filterYearMin = $event"
    />

    <GraphLegend v-if="activeTab === 'graph'" />

    <div v-show="activeTab === 'graph'" class="canvas-container">
      <div v-if="overlayState === 'loading'" class="overlay-message">
        <div class="spinner"></div>
        <p>Loading citation graph…</p>
      </div>
      <div v-else-if="overlayState === 'syncing'" class="overlay-message">
        <div class="spinner"></div>
        <p>Syncing citation data from Semantic Scholar…</p>
        <p class="sync-hint">This may take a few seconds on first visit.</p>
      </div>
      <div v-else-if="overlayState === 'error'" class="overlay-message">
        <p class="error-text">{{ error }}</p>
        <router-link :to="{ name: 'entry', params: { id: entryId } }" class="action-link">
          ← Go to entry detail
        </router-link>
      </div>
      <canvas ref="canvasRef" class="graph-canvas"></canvas>
    </div>

    <GraphAggregateTable
      v-if="activeTab === 'prior'"
      title="Prior Works"
      description="Papers most frequently cited by the papers in this graph — the intellectual foundations of this research area."
      empty-label="No prior works found. This may happen if citation data is still syncing."
      :papers="graphData?.prior_works ?? []"
      :format-authors="formatAuthors"
      :format-count="fmtCount"
      @select-paper="paper => paper.entry_id ? goToEntry(paper.entry_id) : openOnS2(paper.id)"
    />

    <GraphAggregateTable
      v-if="activeTab === 'derivative'"
      title="Derivative Works"
      description="Papers that cite many papers in this graph — recent surveys and state-of-the-art developments."
      empty-label="No derivative works found. This may happen if citation data is still syncing."
      :papers="graphData?.derivative_works ?? []"
      :format-authors="formatAuthors"
      :format-count="fmtCount"
      @select-paper="paper => paper.entry_id ? goToEntry(paper.entry_id) : openOnS2(paper.id)"
    />

    <GraphTooltip
      v-if="activeTab === 'graph' && hoveredNode && !selectedNode"
      :node="hoveredNode"
    />

    <GraphDetailPanel
      v-if="showPanel && selectedNode"
      :node="selectedNode"
      :format-authors="formatAuthors"
      @close="closePanel()"
      @go-to-entry="goToEntry($event)"
      @open-on-s2="openOnS2($event)"
      @recenter="recenterOn($event)"
    />

    <GraphKeyboardHints v-if="activeTab === 'graph'" />
  </div>
</template>
