import { onUnmounted, ref, type Ref } from 'vue'
import type { GraphData, GraphNode } from '@/api/client'
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

  let isDragging = false
  let dragStartX = 0
  let dragStartY = 0
  let cameraStartX = 0
  let cameraStartY = 0
  let onClickCb: ((node: GraphNode) => void) | null = null
  let onDblClickCb: ((node: GraphNode) => void) | null = null

  function init(cvs: HTMLCanvasElement) {
    canvas = cvs
    renderer.init(canvas)
    canvas.addEventListener('mousedown', onMouseDown)
    canvas.addEventListener('mousemove', onMouseMove)
    canvas.addEventListener('mouseup', onMouseUp)
    canvas.addEventListener('mouseleave', onMouseLeave)
    canvas.addEventListener('wheel', onWheel, { passive: false })
    canvas.addEventListener('dblclick', onDblClick)
    window.addEventListener('resize', onResize)
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

  function onMouseDown(event: MouseEvent) {
    const hit = renderer.hitTest(event.offsetX, event.offsetY, simNodes, camera)
    if (hit) {
      selectedNode.value = hit.data
      if (onClickCb) onClickCb(hit.data)
      return
    }

    isDragging = true
    dragStartX = event.clientX
    dragStartY = event.clientY
    cameraStartX = camera.x
    cameraStartY = camera.y
    if (canvas) canvas.style.cursor = 'grabbing'
  }

  function onMouseMove(event: MouseEvent) {
    if (isDragging) {
      camera.x = cameraStartX + (event.clientX - dragStartX) / camera.zoom
      camera.y = cameraStartY + (event.clientY - dragStartY) / camera.zoom
      return
    }

    const hit = renderer.hitTest(event.offsetX, event.offsetY, simNodes, camera)
    hoveredNode.value = hit ? hit.data : null
    if (canvas) canvas.style.cursor = hit ? 'pointer' : 'grab'
  }

  function onMouseUp() {
    isDragging = false
    if (canvas) canvas.style.cursor = 'grab'
  }

  function onMouseLeave() {
    isDragging = false
    hoveredNode.value = null
  }

  function onWheel(event: WheelEvent) {
    event.preventDefault()
    camera.zoom = Math.max(0.1, Math.min(5, camera.zoom * (event.deltaY > 0 ? 0.9 : 1.1)))
  }

  function onDblClick(event: MouseEvent) {
    const hit = renderer.hitTest(event.offsetX, event.offsetY, simNodes, camera)
    if (hit && onDblClickCb) onDblClickCb(hit.data)
  }

  function onResize() {
    if (renderer instanceof CanvasRenderer && canvas) {
      renderer.resize()
    }
  }

  function onNodeClick(cb: (node: GraphNode) => void) {
    onClickCb = cb
  }

  function onNodeDblClick(cb: (node: GraphNode) => void) {
    onDblClickCb = cb
  }

  function resetView() {
    camera.x = 0
    camera.y = 0
    camera.zoom = 1
  }

  function zoomIn() {
    camera.zoom = Math.min(5, camera.zoom * 1.2)
  }

  function zoomOut() {
    camera.zoom = Math.max(0.1, camera.zoom / 1.2)
  }

  function destroy() {
    destroyed = true
    if (animId) cancelAnimationFrame(animId)
    layout.destroy()
    renderer.destroy()

    if (canvas) {
      canvas.removeEventListener('mousedown', onMouseDown)
      canvas.removeEventListener('mousemove', onMouseMove)
      canvas.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('mouseleave', onMouseLeave)
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('dblclick', onDblClick)
    }
    window.removeEventListener('resize', onResize)
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
