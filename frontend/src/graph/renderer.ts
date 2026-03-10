import { citationColor, truncateLabel, yearColor } from '@/graph/colors'
import type { Camera, GraphRenderer, RenderState, SimEdge, SimNode } from '@/graph/types'

export class CanvasRenderer implements GraphRenderer {
  private canvas!: HTMLCanvasElement
  private ctx!: CanvasRenderingContext2D
  private dpr = 1

  init(canvas: HTMLCanvasElement): void {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')!
    this.dpr = window.devicePixelRatio || 1
    this.resize()
  }

  resize(): void {
    const rect = this.canvas.getBoundingClientRect()
    this.canvas.width = rect.width * this.dpr
    this.canvas.height = rect.height * this.dpr
  }

  render(
    nodes: SimNode[],
    edges: SimEdge[],
    camera: Camera,
    state: RenderState
  ): void {
    const ctx = this.ctx
    const width = this.canvas.width
    const height = this.canvas.height
    const dpr = this.dpr

    ctx.clearRect(0, 0, width, height)
    ctx.save()
    ctx.translate(width / 2, height / 2)
    ctx.scale(camera.zoom * dpr, camera.zoom * dpr)
    ctx.translate(camera.x, camera.y)

    for (const edge of edges) {
      const { source, target } = edge
      const isFiltered = state.filteredIds !== null &&
        (!state.filteredIds.has(source.id) || !state.filteredIds.has(target.id))

      const midX = (source.x + target.x) / 2
      const midY = (source.y + target.y) / 2
      const dx = target.x - source.x
      const dy = target.y - source.y
      const distance = Math.sqrt(dx * dx + dy * dy) || 1
      const offset = distance * 0.1
      const cpX = midX - dy * offset / distance
      const cpY = midY + dx * offset / distance

      ctx.beginPath()
      ctx.moveTo(source.x, source.y)
      ctx.quadraticCurveTo(cpX, cpY, target.x, target.y)

      if (isFiltered) {
        ctx.strokeStyle = state.isDark
          ? 'rgba(255, 255, 255, 0.02)'
          : 'rgba(0, 0, 0, 0.02)'
        ctx.lineWidth = 0.5 / camera.zoom
      } else if (state.viewMode === 'similarity' && edge.weight) {
        const weight = edge.weight
        ctx.strokeStyle = state.isDark
          ? `rgba(255, 180, 80, ${0.15 + weight * 0.5})`
          : `rgba(200, 120, 50, ${0.1 + weight * 0.4})`
        ctx.lineWidth = (1 + weight * 4) / camera.zoom
      } else if (edge.is_influential) {
        ctx.strokeStyle = state.isDark
          ? 'rgba(94, 158, 255, 0.5)'
          : 'rgba(59, 130, 246, 0.45)'
        ctx.lineWidth = 2 / camera.zoom
      } else {
        ctx.strokeStyle = state.isDark
          ? 'rgba(255, 255, 255, 0.08)'
          : 'rgba(0, 0, 0, 0.08)'
        ctx.lineWidth = 0.8 / camera.zoom
      }
      ctx.stroke()
    }

    const visibleWidth = width / (camera.zoom * dpr * 2)
    const visibleHeight = height / (camera.zoom * dpr * 2)
    const visibleNodes = nodes.filter((node) =>
      Math.abs(node.x + camera.x) < visibleWidth + 50 &&
      Math.abs(node.y + camera.y) < visibleHeight + 50
    )
    const showAllLabels = state.viewMode === 'similarity' || visibleNodes.length < 30

    for (const node of nodes) {
      const isCenter = node.id === state.centerId
      const isHovered = node.id === state.hoveredId
      const isSelected = node.id === state.selectedId
      const isInLibrary = node.data.in_library
      const isFiltered = state.filteredIds !== null && !state.filteredIds.has(node.id)
      const radius = node.radius
      const color = state.viewMode === 'similarity'
        ? citationColor(node.data.citation_count, state.isDark)
        : yearColor(node.data.year, state.isDark)

      ctx.beginPath()
      ctx.arc(node.x, node.y, radius, 0, Math.PI * 2)
      if (isFiltered) {
        ctx.globalAlpha = 0.12
      }
      ctx.fillStyle = color
      ctx.fill()

      if (isInLibrary) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + 2.5 / camera.zoom, 0, Math.PI * 2)
        ctx.strokeStyle = state.isDark ? '#5E9EFF' : '#3B82F6'
        ctx.lineWidth = 2.5 / camera.zoom
        ctx.stroke()
      }

      if (isCenter) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + 5 / camera.zoom, 0, Math.PI * 2)
        ctx.strokeStyle = state.isDark ? '#F5F5F7' : '#1A1A1A'
        ctx.lineWidth = 2.5 / camera.zoom
        ctx.stroke()
      }

      if (isHovered || isSelected) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, radius + 4 / camera.zoom, 0, Math.PI * 2)
        ctx.strokeStyle = state.isDark
          ? 'rgba(94, 158, 255, 0.8)'
          : 'rgba(59, 130, 246, 0.8)'
        ctx.lineWidth = 3 / camera.zoom
        ctx.stroke()
      }

      const shouldLabel = isCenter || isHovered || isSelected || showAllLabels
      if (shouldLabel) {
        const fontSize = Math.max(10, 12 / camera.zoom)
        ctx.font = `500 ${fontSize}px Inter, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'

        const label = truncateLabel(node.data.title, 40)
        const labelY = node.y + radius + 4 / camera.zoom
        const metrics = ctx.measureText(label)
        const pad = 3 / camera.zoom

        ctx.fillStyle = state.isDark
          ? 'rgba(28, 28, 30, 0.85)'
          : 'rgba(255, 255, 255, 0.9)'
        ctx.fillRect(
          node.x - metrics.width / 2 - pad,
          labelY - pad / 2,
          metrics.width + pad * 2,
          fontSize + pad
        )

        ctx.fillStyle = state.isDark ? '#F5F5F7' : '#1A1A1A'
        ctx.fillText(label, node.x, labelY)
      }

      if (isFiltered) {
        ctx.globalAlpha = 1
      }
    }

    ctx.restore()
  }

  hitTest(
    screenX: number,
    screenY: number,
    nodes: SimNode[],
    camera: Camera
  ): SimNode | null {
    const rect = this.canvas.getBoundingClientRect()
    const worldX = (screenX - rect.width / 2) / camera.zoom - camera.x
    const worldY = (screenY - rect.height / 2) / camera.zoom - camera.y

    let best: SimNode | null = null
    let bestDistance = Infinity
    for (const node of nodes) {
      const dx = node.x - worldX
      const dy = node.y - worldY
      const distance = Math.sqrt(dx * dx + dy * dy)
      if (distance < node.radius + 5 / camera.zoom && distance < bestDistance) {
        best = node
        bestDistance = distance
      }
    }
    return best
  }

  destroy(): void {
    // Canvas 2D has no renderer-specific cleanup.
  }
}
