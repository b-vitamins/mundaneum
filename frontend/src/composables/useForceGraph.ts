import { onUnmounted, ref, type Ref } from 'vue'
import type { GraphData, GraphNode } from '@/api/client'
import { createCanvasInteractionController } from '@/graph/interactions'
import { ForceLayout } from '@/graph/layout'
import { CanvasRenderer } from '@/graph/renderer'
import {
  buildSimEdges,
  buildSimNodes,
  type Camera,
  type GraphLayout,
  type GraphRenderer,
  type SimEdge,
  type SimNode,
  type ViewMode,
} from '@/graph/types'

export function useForceGraph() {
  const hoveredNode = ref<GraphNode | null>(null)
  const selectedNode = ref<GraphNode | null>(null)
  const isSettled = ref(false)
  const viewMode = ref<ViewMode>('citation')

  let canvas: HTMLCanvasElement | null = null
  let simNodes: SimNode[] = []
  let simEdges: SimEdge[] = []
  let centerId = ''
  let rawData: GraphData | null = null
  let nodeMap = new Map<string, SimNode>()
  let filteredIds: Set<string> | null = null
  let layout: GraphLayout = new ForceLayout()
  let renderer: GraphRenderer = new CanvasRenderer()
  let animId = 0
  let destroyed = false

  const camera: Camera = { x: 0, y: 0, zoom: 1 }

  let onClickCb: ((node: GraphNode) => void) | null = null
  let onDblClickCb: ((node: GraphNode) => void) | null = null

  const interactions = createCanvasInteractionController({
    camera,
    hoveredNode: hoveredNode as Ref<GraphNode | null>,
    selectedNode: selectedNode as Ref<GraphNode | null>,
    renderer,
    getNodes: () => simNodes,
    onNodeClick: () => onClickCb,
    onNodeDblClick: () => onDblClickCb,
  })

  function init(cvs: HTMLCanvasElement) {
    canvas = cvs
    renderer.init(canvas)
    interactions.bind(canvas)
  }

  function buildEdges(mode: ViewMode) {
    if (!rawData) return
    simEdges = buildSimEdges(rawData, nodeMap, mode)
  }

  function startLoop() {
    if (animId) cancelAnimationFrame(animId)

    function frame() {
      if (destroyed) return

      isSettled.value = layout.tick(16)
      renderer.render(simNodes, simEdges, camera, {
        centerId,
        hoveredId: hoveredNode.value?.id ?? null,
        selectedId: selectedNode.value?.id ?? null,
        isDark: document.documentElement.getAttribute('data-theme') === 'dark',
        viewMode: viewMode.value,
        filteredIds,
      })

      animId = requestAnimationFrame(frame)
    }

    animId = requestAnimationFrame(frame)
  }

  function loadData(data: GraphData) {
    rawData = data
    const simState = buildSimNodes(data)
    centerId = simState.centerId
    nodeMap = simState.nodeMap
    simNodes = simState.simNodes

    viewMode.value = 'similarity'
    isSettled.value = false
    buildEdges('similarity')
    layout.init(simNodes, simEdges)
    camera.x = 0
    camera.y = 0
    camera.zoom = 1
    startLoop()
  }

  function setViewMode(mode: ViewMode) {
    if (mode === viewMode.value) return
    viewMode.value = mode
    buildEdges(mode)
    isSettled.value = false
    layout.init(simNodes, simEdges)
    for (const node of simNodes) {
      node.vx = 0
      node.vy = 0
    }
  }

  function setFilter(predicate: ((node: GraphNode) => boolean) | null) {
    filteredIds = predicate
      ? new Set(simNodes.filter(node => predicate(node.data)).map(node => node.id))
      : null
  }

  function getSimNodes(): SimNode[] {
    return simNodes
  }

  function onNodeClick(cb: (node: GraphNode) => void) {
    onClickCb = cb
  }

  function onNodeDblClick(cb: (node: GraphNode) => void) {
    onDblClickCb = cb
  }

  function resetView() {
    interactions.resetView()
  }

  function zoomIn() {
    interactions.zoomIn()
  }

  function zoomOut() {
    interactions.zoomOut()
  }

  function destroy() {
    destroyed = true
    if (animId) cancelAnimationFrame(animId)
    layout.destroy()
    renderer.destroy()
    interactions.unbind()
  }

  onUnmounted(destroy)

  return {
    hoveredNode: hoveredNode as Ref<GraphNode | null>,
    selectedNode: selectedNode as Ref<GraphNode | null>,
    isSettled,
    viewMode,
    init,
    loadData,
    destroy,
    resetView,
    zoomIn,
    zoomOut,
    onNodeClick,
    onNodeDblClick,
    setViewMode,
    setFilter,
    getSimNodes,
  }
}
