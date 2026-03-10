import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type GraphData, type GraphNode } from '@/api/client'
import { useForceGraph } from '@/composables/useForceGraph'

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
  const activeTab = ref<'graph' | 'prior' | 'derivative'>('graph')
  const filterKeyword = ref('')
  const yearMin = ref(1990)
  const yearMax = ref(2026)
  const filterYearMin = ref(1990)
  const filterYearMax = ref(2026)
  const syncing = ref(false)

  let filterTimer: ReturnType<typeof setTimeout> | null = null

  const yearHistogram = computed(() => {
    if (!graphData.value) return []
    const counts: Record<number, number> = {}
    for (const node of graphData.value.nodes) {
      if (node.year) counts[node.year] = (counts[node.year] || 0) + 1
    }
    const histogram: { year: number; count: number }[] = []
    for (let year = yearMin.value; year <= yearMax.value; year += 1) {
      histogram.push({ year, count: counts[year] || 0 })
    }
    return histogram
  })

  const maxHistCount = computed(() => Math.max(1, ...yearHistogram.value.map(item => item.count)))

  const sliceAndLoad = (data: GraphData, nodeCount: number) => {
    const centerNode = data.nodes.find(node => node.id === data.center_id)
    const otherNodes = data.nodes.filter(node => node.id !== data.center_id)
    const nodes = centerNode
      ? [centerNode, ...otherNodes.slice(0, nodeCount - 1)]
      : otherNodes.slice(0, nodeCount)
    const nodeIds = new Set(nodes.map(node => node.id))

    const slicedData: GraphData = {
      ...data,
      nodes,
      edges: data.edges.filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
      similarity_edges: data.similarity_edges.filter(edge => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
    }

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

      const years = data.nodes.map(node => node.year).filter(Boolean) as number[]
      if (years.length > 0) {
        yearMin.value = Math.min(...years)
        yearMax.value = Math.max(...years)
        filterYearMin.value = yearMin.value
        filterYearMax.value = yearMax.value
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
      if (node.year && (node.year < filterYearMin.value || node.year > filterYearMax.value)) return false
      if (keyword) {
        const text = [node.title, ...node.authors, node.venue || ''].join(' ').toLowerCase()
        if (!text.includes(keyword)) return false
      }
      return true
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

  function formatAuthors(authors: string[]): string {
    if (authors.length <= 3) return authors.join(', ')
    return `${authors.slice(0, 3).join(', ')} +${authors.length - 3}`
  }

  function fmtCount(value: number): string {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
    return value.toString()
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

  return {
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
    graph,
    graphData,
    loading,
    maxHistCount,
    maxNodes,
    openOnS2,
    recenterOn,
    router,
    showPanel,
    syncing,
    yearHistogram,
    yearMax,
    yearMin,
  }
}
