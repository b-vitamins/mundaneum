import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type GraphData, type GraphNode } from '@/api/client'
import { useForceGraph } from '@/composables/useForceGraph'
import type { GraphOverlayState, GraphExplorerTab } from '@/features/graph/types'
import {
  buildYearHistogram,
  formatGraphAuthors,
  formatGraphCount,
  getYearBounds,
  matchesGraphFilter,
  sliceGraphData,
} from '@/graph/data'

export function useGraphExplorer() {
  const route = useRoute()
  const router = useRouter()
  const graph = useForceGraph()
  const canvasRef = ref<HTMLCanvasElement | null>(null)
  const entryId = computed(() => route.params.id as string)

  const loading = ref(true)
  const error = ref('')
  const depth = ref(1)
  const maxNodes = ref(40)
  const fullGraphData = ref<GraphData | null>(null)
  const showPanel = ref(true)
  const graphData = ref<GraphData | null>(null)
  const activeTab = ref<GraphExplorerTab>('graph')
  const filterKeyword = ref('')
  const yearMin = ref(1990)
  const yearMax = ref(2026)
  const filterYearMin = ref(1990)
  const filterYearMax = ref(2026)
  const syncing = ref(false)

  let filterTimer: ReturnType<typeof setTimeout> | null = null

  const yearHistogram = computed(() => {
    return buildYearHistogram(graphData.value, yearMin.value, yearMax.value)
  })

  const maxHistCount = computed(() => Math.max(1, ...yearHistogram.value.map(item => item.count)))

  const sliceAndLoad = (data: GraphData, nodeCount: number) => {
    const slicedData = sliceGraphData(data, nodeCount)
    graphData.value = slicedData
    graph.loadData(slicedData)
  }

  const fetchGraph = async () => {
    loading.value = true
    error.value = ''
    syncing.value = false

    try {
      const data = await api.getGraph(entryId.value, depth.value, 200)
      fullGraphData.value = data

      if (data.nodes.length === 0) {
        error.value = (data as { message?: string }).message || 'No citation data available for this entry.'
        return
      }

      const bounds = getYearBounds(data)
      if (bounds) {
        yearMin.value = bounds.min
        yearMax.value = bounds.max
        filterYearMin.value = bounds.min
        filterYearMax.value = bounds.max
      }

      sliceAndLoad(data, maxNodes.value)
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load graph data.'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  const applyFilter = () => {
    const keyword = filterKeyword.value.trim().toLowerCase()
    const noYearFilter = filterYearMin.value <= yearMin.value && filterYearMax.value >= yearMax.value
    const noKeywordFilter = keyword === ''

    if (noYearFilter && noKeywordFilter) {
      graph.setFilter(null)
      return
    }

    graph.setFilter(node => {
      return matchesGraphFilter(
        node,
        keyword,
        filterYearMin.value,
        filterYearMax.value
      )
    })
  }

  function onKeydown(event: KeyboardEvent) {
    if (event.target instanceof HTMLInputElement) return

    switch (event.key) {
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

  function goToEntry(id: string) {
    router.push({ name: 'entry', params: { id } })
  }

  function openOnS2(s2Id: string) {
    window.open(`https://www.semanticscholar.org/paper/${s2Id}`, '_blank')
  }

  function recenterOn(node: GraphNode) {
    if (node.in_library && node.entry_id) {
      router.push({ name: 'graph', params: { id: node.entry_id } })
    }
  }

  function closePanel() {
    graph.selectedNode.value = null
    showPanel.value = false
  }

  function formatAuthors(authors: string[]): string {
    return formatGraphAuthors(authors)
  }

  function fmtCount(value: number): string {
    return formatGraphCount(value)
  }

  graph.onNodeClick(() => {
    showPanel.value = true
  })

  graph.onNodeDblClick((node: GraphNode) => {
    if (node.in_library && node.entry_id) {
      router.push({ name: 'graph', params: { id: node.entry_id } })
    }
  })

  onMounted(() => {
    if (canvasRef.value) graph.init(canvasRef.value)
    fetchGraph()
    window.addEventListener('keydown', onKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown)
    if (filterTimer) clearTimeout(filterTimer)
  })

  watch(depth, fetchGraph)
  watch(entryId, fetchGraph)
  watch(maxNodes, () => {
    if (fullGraphData.value && fullGraphData.value.nodes.length > 0) {
      sliceAndLoad(fullGraphData.value, maxNodes.value)
    }
  })
  watch([filterYearMin, filterYearMax], applyFilter)
  watch(filterKeyword, () => {
    const value = filterKeyword.value
    if (filterTimer) clearTimeout(filterTimer)
    filterTimer = setTimeout(() => {
      if (filterKeyword.value === value) applyFilter()
    }, 200)
  })

  const overlayState = computed<GraphOverlayState>(() => {
    if (loading.value) return 'loading'
    if (syncing.value) return 'syncing'
    if (error.value) return 'error'
    return null
  })

  return {
    activeTab,
    canvasRef,
    closePanel,
    depth,
    entryId,
    error,
    filterKeyword,
    filterYearMax,
    filterYearMin,
    fmtCount,
    formatAuthors,
    goToEntry,
    graph,
    graphData,
    loading,
    maxHistCount,
    maxNodes,
    overlayState,
    openOnS2,
    recenterOn,
    router,
    selectedNode: graph.selectedNode,
    showPanel,
    syncing,
    hoveredNode: graph.hoveredNode,
    setViewMode: graph.setViewMode,
    resetView: graph.resetView,
    zoomIn: graph.zoomIn,
    zoomOut: graph.zoomOut,
    viewMode: graph.viewMode,
    yearHistogram,
    yearMax,
    yearMin,
  }
}
