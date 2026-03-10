import type { Ref } from 'vue'
import type { GraphNode } from '@/api/client'
import { CanvasRenderer } from '@/graph/renderer'
import type { Camera, GraphRenderer, SimNode } from '@/graph/types'

interface InteractionOptions {
  camera: Camera
  hoveredNode: Ref<GraphNode | null>
  selectedNode: Ref<GraphNode | null>
  renderer: GraphRenderer
  getNodes: () => SimNode[]
  onNodeClick: () => ((node: GraphNode) => void) | null
  onNodeDblClick: () => ((node: GraphNode) => void) | null
}

export function createCanvasInteractionController(options: InteractionOptions) {
  let canvas: HTMLCanvasElement | null = null
  let isDragging = false
  let dragStartX = 0
  let dragStartY = 0
  let cameraStartX = 0
  let cameraStartY = 0

  const onMouseDown = (event: MouseEvent) => {
    const hit = options.renderer.hitTest(
      event.offsetX,
      event.offsetY,
      options.getNodes(),
      options.camera
    )
    if (hit) {
      options.selectedNode.value = hit.data
      options.onNodeClick()?.(hit.data)
      return
    }

    isDragging = true
    dragStartX = event.clientX
    dragStartY = event.clientY
    cameraStartX = options.camera.x
    cameraStartY = options.camera.y
    if (canvas) {
      canvas.style.cursor = 'grabbing'
    }
  }

  const onMouseMove = (event: MouseEvent) => {
    if (isDragging) {
      options.camera.x = cameraStartX + (event.clientX - dragStartX) / options.camera.zoom
      options.camera.y = cameraStartY + (event.clientY - dragStartY) / options.camera.zoom
      return
    }

    const hit = options.renderer.hitTest(
      event.offsetX,
      event.offsetY,
      options.getNodes(),
      options.camera
    )
    options.hoveredNode.value = hit ? hit.data : null
    if (canvas) {
      canvas.style.cursor = hit ? 'pointer' : 'grab'
    }
  }

  const onMouseUp = () => {
    isDragging = false
    if (canvas) {
      canvas.style.cursor = 'grab'
    }
  }

  const onMouseLeave = () => {
    isDragging = false
    options.hoveredNode.value = null
  }

  const onWheel = (event: WheelEvent) => {
    event.preventDefault()
    options.camera.zoom = Math.max(
      0.1,
      Math.min(5, options.camera.zoom * (event.deltaY > 0 ? 0.9 : 1.1))
    )
  }

  const onDblClick = (event: MouseEvent) => {
    const hit = options.renderer.hitTest(
      event.offsetX,
      event.offsetY,
      options.getNodes(),
      options.camera
    )
    if (hit) {
      options.onNodeDblClick()?.(hit.data)
    }
  }

  const onResize = () => {
    if (options.renderer instanceof CanvasRenderer && canvas) {
      options.renderer.resize()
    }
  }

  const bind = (element: HTMLCanvasElement) => {
    canvas = element
    canvas.addEventListener('mousedown', onMouseDown)
    canvas.addEventListener('mousemove', onMouseMove)
    canvas.addEventListener('mouseup', onMouseUp)
    canvas.addEventListener('mouseleave', onMouseLeave)
    canvas.addEventListener('wheel', onWheel, { passive: false })
    canvas.addEventListener('dblclick', onDblClick)
    window.addEventListener('resize', onResize)
  }

  const unbind = () => {
    if (canvas) {
      canvas.removeEventListener('mousedown', onMouseDown)
      canvas.removeEventListener('mousemove', onMouseMove)
      canvas.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('mouseleave', onMouseLeave)
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('dblclick', onDblClick)
    }
    window.removeEventListener('resize', onResize)
    canvas = null
  }

  const resetView = () => {
    options.camera.x = 0
    options.camera.y = 0
    options.camera.zoom = 1
  }

  const zoomIn = () => {
    options.camera.zoom = Math.min(5, options.camera.zoom * 1.2)
  }

  const zoomOut = () => {
    options.camera.zoom = Math.max(0.1, options.camera.zoom / 1.2)
  }

  return {
    bind,
    resetView,
    unbind,
    zoomIn,
    zoomOut,
  }
}
