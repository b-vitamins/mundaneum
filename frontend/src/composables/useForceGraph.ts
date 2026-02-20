/**
 * useForceGraph — Composable for interactive force-directed graph visualization.
 *
 * Architecture (Sussman "Design for Flexibility"):
 * ─────────────────────────────────────────────────
 * Two protocol layers, independently replaceable:
 *
 *   GraphLayout  — computes positions each frame (V1: CPU Barnes-Hut)
 *   GraphRenderer — draws current state (V1: Canvas 2D)
 *
 * This composable is the orchestrator: owns the animation loop,
 * event routing, and public API. It delegates all physics to the
 * layout and all drawing to the renderer.
 *
 * Future drop-in replacements:
 *   - GPUForceLayout (WebGPU compute shader)
 *   - WebGPURenderer (instanced mesh rendering)
 * can implement the same interfaces without touching this file.
 */

import { ref, onUnmounted, type Ref } from 'vue'
import type { GraphNode, GraphData } from '@/api/client'

// ──────────────────────────────────────────────────────────
// Simulation types — internal, mutable state for the engine
// ──────────────────────────────────────────────────────────

export interface SimNode {
    id: string
    x: number
    y: number
    vx: number
    vy: number
    radius: number
    // Original data
    data: GraphNode
}

export interface SimEdge {
    source: SimNode
    target: SimNode
    is_influential: boolean
}

export interface Camera {
    x: number       // offset
    y: number
    zoom: number
}

// ──────────────────────────────────────────────────────────
// Protocol: GraphLayout
// ──────────────────────────────────────────────────────────

export interface GraphLayout {
    init(nodes: SimNode[], edges: SimEdge[]): void
    tick(dt: number): boolean  // returns true when settled
    destroy(): void
}

// ──────────────────────────────────────────────────────────
// Protocol: GraphRenderer
// ──────────────────────────────────────────────────────────

export interface GraphRenderer {
    init(canvas: HTMLCanvasElement): void
    render(
        nodes: SimNode[],
        edges: SimEdge[],
        camera: Camera,
        state: RenderState
    ): void
    hitTest(
        x: number,
        y: number,
        nodes: SimNode[],
        camera: Camera
    ): SimNode | null
    destroy(): void
}

export interface RenderState {
    centerId: string
    hoveredId: string | null
    selectedId: string | null
    isDark: boolean
}

// ──────────────────────────────────────────────────────────
// V1 Layout: CPU Force Simulation with Barnes-Hut Quadtree
// ──────────────────────────────────────────────────────────

interface QuadNode {
    x: number
    y: number
    mass: number
    // Children: NW, NE, SW, SE
    children: (QuadNode | null)[]
    body: SimNode | null
    isLeaf: boolean
    cx: number  // center of mass x
    cy: number  // center of mass y
    size: number  // width of this quad
}

function buildQuadtree(nodes: SimNode[]): QuadNode | null {
    if (nodes.length === 0) return null

    // Find bounds
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
    for (const n of nodes) {
        if (n.x < minX) minX = n.x
        if (n.x > maxX) maxX = n.x
        if (n.y < minY) minY = n.y
        if (n.y > maxY) maxY = n.y
    }

    const pad = 10
    const size = Math.max(maxX - minX, maxY - minY) + pad * 2
    const root = createQuad(minX - pad, minY - pad, size)

    for (const n of nodes) {
        insertNode(root, n)
    }

    return root
}

function createQuad(x: number, y: number, size: number): QuadNode {
    return {
        x, y, size,
        mass: 0, cx: 0, cy: 0,
        children: [null, null, null, null],
        body: null, isLeaf: true,
    }
}

function insertNode(quad: QuadNode, node: SimNode) {
    if (quad.mass === 0 && quad.isLeaf) {
        quad.body = node
        quad.mass = 1
        quad.cx = node.x
        quad.cy = node.y
        return
    }

    if (quad.isLeaf && quad.body) {
        // Split: push existing body down
        const existing = quad.body
        quad.body = null
        quad.isLeaf = false
        insertIntoChild(quad, existing)
    }

    // Update center of mass
    const totalMass = quad.mass + 1
    quad.cx = (quad.cx * quad.mass + node.x) / totalMass
    quad.cy = (quad.cy * quad.mass + node.y) / totalMass
    quad.mass = totalMass

    insertIntoChild(quad, node)
}

function insertIntoChild(quad: QuadNode, node: SimNode) {
    const halfSize = quad.size / 2
    const midX = quad.x + halfSize
    const midY = quad.y + halfSize

    let idx: number
    if (node.x < midX) {
        idx = node.y < midY ? 0 : 2  // NW or SW
    } else {
        idx = node.y < midY ? 1 : 3  // NE or SE
    }

    if (!quad.children[idx]) {
        const cx = idx % 2 === 0 ? quad.x : midX
        const cy = idx < 2 ? quad.y : midY
        quad.children[idx] = createQuad(cx, cy, halfSize)
    }

    insertNode(quad.children[idx]!, node)
}

function computeRepulsion(
    node: SimNode, quad: QuadNode | null,
    theta: number, strength: number
) {
    if (!quad || quad.mass === 0) return

    const dx = quad.cx - node.x
    const dy = quad.cy - node.y
    const dist = Math.sqrt(dx * dx + dy * dy) || 1

    // If far enough, treat as single body
    if (quad.size / dist < theta || quad.isLeaf) {
        if (quad.body === node) return
        const force = -strength * quad.mass / (dist * dist)
        node.vx += force * dx / dist
        node.vy += force * dy / dist
        return
    }

    // Otherwise recurse into children
    for (const child of quad.children) {
        if (child) computeRepulsion(node, child, theta, strength)
    }
}

class ForceLayout implements GraphLayout {
    private nodes: SimNode[] = []
    private edges: SimEdge[] = []
    private alpha = 1.0
    private alphaDecay = 0.02
    private alphaMin = 0.001

    // Force parameters
    private repulsionStrength = 300
    private springStrength = 0.05
    private springLength = 120
    private centerStrength = 0.01
    private damping = 0.85
    private theta = 0.9  // Barnes-Hut threshold

    init(nodes: SimNode[], edges: SimEdge[]) {
        this.nodes = nodes
        this.edges = edges
        this.alpha = 1.0

        // Initialize positions in a circle
        const n = nodes.length
        for (let i = 0; i < n; i++) {
            const angle = (2 * Math.PI * i) / n
            const r = Math.sqrt(n) * 30
            nodes[i].x = Math.cos(angle) * r
            nodes[i].y = Math.sin(angle) * r
            nodes[i].vx = 0
            nodes[i].vy = 0
        }
    }

    tick(_dt: number): boolean {
        if (this.alpha < this.alphaMin) return true

        const nodes = this.nodes

        // 1. Charge repulsion via Barnes-Hut
        const tree = buildQuadtree(nodes)
        for (const node of nodes) {
            computeRepulsion(node, tree, this.theta, this.repulsionStrength * this.alpha)
        }

        // 2. Spring forces (edges)
        for (const edge of this.edges) {
            const dx = edge.target.x - edge.source.x
            const dy = edge.target.y - edge.source.y
            const dist = Math.sqrt(dx * dx + dy * dy) || 1
            const force = (dist - this.springLength) * this.springStrength * this.alpha
            const fx = force * dx / dist
            const fy = force * dy / dist
            edge.source.vx += fx
            edge.source.vy += fy
            edge.target.vx -= fx
            edge.target.vy -= fy
        }

        // 3. Center gravity
        for (const node of nodes) {
            node.vx -= node.x * this.centerStrength * this.alpha
            node.vy -= node.y * this.centerStrength * this.alpha
        }

        // 4. Velocity verlet integration + damping
        for (const node of nodes) {
            node.vx *= this.damping
            node.vy *= this.damping
            node.x += node.vx
            node.y += node.vy
        }

        // 5. Cool down
        this.alpha *= (1 - this.alphaDecay)

        return false
    }

    destroy() {
        this.nodes = []
        this.edges = []
    }
}

// ──────────────────────────────────────────────────────────
// V1 Renderer: Canvas 2D
// ──────────────────────────────────────────────────────────

class CanvasRenderer implements GraphRenderer {
    private canvas!: HTMLCanvasElement
    private ctx!: CanvasRenderingContext2D
    private dpr = 1

    init(canvas: HTMLCanvasElement) {
        this.canvas = canvas
        this.ctx = canvas.getContext('2d')!
        this.dpr = window.devicePixelRatio || 1
        this.resize()
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect()
        this.canvas.width = rect.width * this.dpr
        this.canvas.height = rect.height * this.dpr
    }

    render(
        nodes: SimNode[],
        edges: SimEdge[],
        camera: Camera,
        state: RenderState
    ) {
        const ctx = this.ctx
        const w = this.canvas.width
        const h = this.canvas.height
        const dpr = this.dpr

        ctx.clearRect(0, 0, w, h)
        ctx.save()

        // Apply camera transform
        ctx.translate(w / 2, h / 2)
        ctx.scale(camera.zoom * dpr, camera.zoom * dpr)
        ctx.translate(camera.x, camera.y)

        // ── Draw edges ──
        for (const edge of edges) {
            const { source: s, target: t } = edge

            // Curved bezier for visual clarity
            const midX = (s.x + t.x) / 2
            const midY = (s.y + t.y) / 2
            const dx = t.x - s.x
            const dy = t.y - s.y
            const offset = Math.sqrt(dx * dx + dy * dy) * 0.1
            const cpX = midX - dy * offset / (Math.sqrt(dx * dx + dy * dy) || 1)
            const cpY = midY + dx * offset / (Math.sqrt(dx * dx + dy * dy) || 1)

            ctx.beginPath()
            ctx.moveTo(s.x, s.y)
            ctx.quadraticCurveTo(cpX, cpY, t.x, t.y)

            if (edge.is_influential) {
                ctx.strokeStyle = state.isDark
                    ? 'rgba(94, 158, 255, 0.5)'
                    : 'rgba(59, 130, 246, 0.45)'
                ctx.lineWidth = 2.0 / camera.zoom
            } else {
                ctx.strokeStyle = state.isDark
                    ? 'rgba(255, 255, 255, 0.08)'
                    : 'rgba(0, 0, 0, 0.08)'
                ctx.lineWidth = 0.8 / camera.zoom
            }
            ctx.stroke()
        }

        // ── Draw nodes ──
        // Determine visible area for LOD
        const visW = w / (camera.zoom * dpr * 2)
        const visH = h / (camera.zoom * dpr * 2)
        const visibleNodes = nodes.filter(n =>
            Math.abs(n.x + camera.x) < visW + 50 &&
            Math.abs(n.y + camera.y) < visH + 50
        )
        const showAllLabels = visibleNodes.length < 30

        for (const node of nodes) {
            const isCenter = node.id === state.centerId
            const isHovered = node.id === state.hoveredId
            const isSelected = node.id === state.selectedId
            const isInLibrary = node.data.in_library

            const r = node.radius

            // Year-based color
            const color = yearColor(node.data.year, state.isDark)

            // Draw node circle
            ctx.beginPath()
            ctx.arc(node.x, node.y, r, 0, Math.PI * 2)

            // Fill
            ctx.fillStyle = color
            ctx.fill()

            // In-library accent ring
            if (isInLibrary) {
                ctx.beginPath()
                ctx.arc(node.x, node.y, r + 2.5 / camera.zoom, 0, Math.PI * 2)
                ctx.strokeStyle = state.isDark ? '#5E9EFF' : '#3B82F6'
                ctx.lineWidth = 2.5 / camera.zoom
                ctx.stroke()
            }

            // Center node highlight
            if (isCenter) {
                ctx.beginPath()
                ctx.arc(node.x, node.y, r + 5 / camera.zoom, 0, Math.PI * 2)
                ctx.strokeStyle = state.isDark ? '#F5F5F7' : '#1A1A1A'
                ctx.lineWidth = 2.5 / camera.zoom
                ctx.stroke()
            }

            // Hover / selection glow
            if (isHovered || isSelected) {
                ctx.beginPath()
                ctx.arc(node.x, node.y, r + 4 / camera.zoom, 0, Math.PI * 2)
                ctx.strokeStyle = state.isDark ? 'rgba(94, 158, 255, 0.8)' : 'rgba(59, 130, 246, 0.8)'
                ctx.lineWidth = 3 / camera.zoom
                ctx.stroke()
            }

            // Labels: always for center/hovered/selected, LOD for others
            const shouldLabel = isCenter || isHovered || isSelected || showAllLabels
            if (shouldLabel) {
                const fontSize = Math.max(10, 12 / camera.zoom)
                ctx.font = `500 ${fontSize}px Inter, sans-serif`
                ctx.textAlign = 'center'
                ctx.textBaseline = 'top'

                const label = truncateLabel(node.data.title, 40)
                const labelY = node.y + r + 4 / camera.zoom

                // Label background
                const metrics = ctx.measureText(label)
                const pad = 3 / camera.zoom
                ctx.fillStyle = state.isDark ? 'rgba(28, 28, 30, 0.85)' : 'rgba(255, 255, 255, 0.9)'
                ctx.fillRect(
                    node.x - metrics.width / 2 - pad,
                    labelY - pad / 2,
                    metrics.width + pad * 2,
                    fontSize + pad
                )

                ctx.fillStyle = state.isDark ? '#F5F5F7' : '#1A1A1A'
                ctx.fillText(label, node.x, labelY)
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
        // Convert screen coords to world coords
        const rect = this.canvas.getBoundingClientRect()
        const wx = (screenX - rect.width / 2) / camera.zoom - camera.x
        const wy = (screenY - rect.height / 2) / camera.zoom - camera.y

        // Find closest node within radius
        let best: SimNode | null = null
        let bestDist = Infinity
        for (const node of nodes) {
            const dx = node.x - wx
            const dy = node.y - wy
            const dist = Math.sqrt(dx * dx + dy * dy)
            if (dist < node.radius + 5 / camera.zoom && dist < bestDist) {
                best = node
                bestDist = dist
            }
        }
        return best
    }

    destroy() {
        // Nothing to clean up for Canvas 2D
    }
}

// ── Color helpers ──

function yearColor(year: number | null, isDark: boolean): string {
    if (!year) return isDark ? 'rgba(100, 100, 110, 0.8)' : 'rgba(150, 150, 160, 0.8)'

    // Map year to hue: older (1990) = cool blue (220), newer (2026) = warm orange (30)
    const minYear = 1990
    const maxYear = 2026
    const t = Math.max(0, Math.min(1, (year - minYear) / (maxYear - minYear)))

    // Hue: 220 (blue) → 30 (orange)
    const hue = 220 - t * 190
    const saturation = isDark ? 60 : 55
    const lightness = isDark ? 55 : 50

    return `hsla(${hue}, ${saturation}%, ${lightness}%, 0.9)`
}

function truncateLabel(text: string, maxLen: number): string {
    if (text.length <= maxLen) return text
    return text.slice(0, maxLen - 1) + '…'
}

// ──────────────────────────────────────────────────────────
// Composable: useForceGraph
// ──────────────────────────────────────────────────────────

export function useForceGraph() {
    // State
    const hoveredNode = ref<GraphNode | null>(null)
    const selectedNode = ref<GraphNode | null>(null)
    const isSettled = ref(false)

    // Internals
    let canvas: HTMLCanvasElement | null = null
    let simNodes: SimNode[] = []
    let simEdges: SimEdge[] = []
    let centerId = ''
    let layout: GraphLayout = new ForceLayout()
    let renderer: GraphRenderer = new CanvasRenderer()
    let animId = 0
    let destroyed = false

    // Camera
    const camera: Camera = { x: 0, y: 0, zoom: 1 }

    // Drag state
    let isDragging = false
    let dragStartX = 0
    let dragStartY = 0
    let cameraStartX = 0
    let cameraStartY = 0

    // Callbacks
    let onClickCb: ((node: GraphNode) => void) | null = null
    let onDblClickCb: ((node: GraphNode) => void) | null = null

    function init(cvs: HTMLCanvasElement) {
        canvas = cvs
        renderer.init(canvas)

        // Event listeners
        canvas.addEventListener('mousedown', onMouseDown)
        canvas.addEventListener('mousemove', onMouseMove)
        canvas.addEventListener('mouseup', onMouseUp)
        canvas.addEventListener('mouseleave', onMouseLeave)
        canvas.addEventListener('wheel', onWheel, { passive: false })
        canvas.addEventListener('dblclick', onDblClick)
        window.addEventListener('resize', onResize)
    }

    function loadData(data: GraphData) {
        centerId = data.center_id

        // Build SimNodes
        const nodeMap = new Map<string, SimNode>()
        simNodes = data.nodes.map(n => {
            const r = 4 + 2 * Math.log2(Math.max(1, n.citation_count))
            const sn: SimNode = {
                id: n.id,
                x: 0, y: 0,
                vx: 0, vy: 0,
                radius: Math.min(r, 25),
                data: n,
            }
            nodeMap.set(n.id, sn)
            return sn
        })

        // Build SimEdges (only for edges where both nodes exist)
        simEdges = []
        for (const e of data.edges) {
            const src = nodeMap.get(e.source)
            const tgt = nodeMap.get(e.target)
            if (src && tgt) {
                simEdges.push({
                    source: src,
                    target: tgt,
                    is_influential: e.is_influential,
                })
            }
        }

        // Position center node at origin
        const centerNode = nodeMap.get(centerId)
        if (centerNode) {
            centerNode.x = 0
            centerNode.y = 0
        }

        // Init layout
        isSettled.value = false
        layout.init(simNodes, simEdges)

        // Reset camera
        camera.x = 0
        camera.y = 0
        camera.zoom = 1

        // Start animation
        startLoop()
    }

    function startLoop() {
        if (animId) cancelAnimationFrame(animId)

        function frame() {
            if (destroyed) return

            const settled = layout.tick(16)
            isSettled.value = settled

            const isDark = document.documentElement.getAttribute('data-theme') === 'dark'

            renderer.render(simNodes, simEdges, camera, {
                centerId,
                hoveredId: hoveredNode.value?.id ?? null,
                selectedId: selectedNode.value?.id ?? null,
                isDark,
            })

            animId = requestAnimationFrame(frame)
        }

        animId = requestAnimationFrame(frame)
    }

    // ── Event handlers ──

    function onMouseDown(e: MouseEvent) {
        const hit = renderer.hitTest(e.offsetX, e.offsetY, simNodes, camera)
        if (hit) {
            selectedNode.value = hit.data
            if (onClickCb) onClickCb(hit.data)
        } else {
            // Start pan
            isDragging = true
            dragStartX = e.clientX
            dragStartY = e.clientY
            cameraStartX = camera.x
            cameraStartY = camera.y
            if (canvas) canvas.style.cursor = 'grabbing'
        }
    }

    function onMouseMove(e: MouseEvent) {
        if (isDragging) {
            camera.x = cameraStartX + (e.clientX - dragStartX) / camera.zoom
            camera.y = cameraStartY + (e.clientY - dragStartY) / camera.zoom
            return
        }

        const hit = renderer.hitTest(e.offsetX, e.offsetY, simNodes, camera)
        hoveredNode.value = hit ? hit.data : null
        if (canvas) canvas.style.cursor = hit ? 'pointer' : 'grab'
    }

    function onMouseUp(_e: MouseEvent) {
        isDragging = false
        if (canvas) canvas.style.cursor = 'grab'
    }

    function onMouseLeave(_e: MouseEvent) {
        isDragging = false
        hoveredNode.value = null
    }

    function onWheel(e: WheelEvent) {
        e.preventDefault()
        const factor = e.deltaY > 0 ? 0.9 : 1.1
        camera.zoom = Math.max(0.1, Math.min(5, camera.zoom * factor))
    }

    function onDblClick(e: MouseEvent) {
        const hit = renderer.hitTest(e.offsetX, e.offsetY, simNodes, camera)
        if (hit && onDblClickCb) {
            onDblClickCb(hit.data)
        }
    }

    function onResize() {
        if (renderer && canvas) {
            (renderer as CanvasRenderer).resize()
        }
    }

    // ── Public API ──

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
        // Reactive state
        hoveredNode: hoveredNode as Ref<GraphNode | null>,
        selectedNode: selectedNode as Ref<GraphNode | null>,
        isSettled,

        // Methods
        init,
        loadData,
        destroy,
        resetView,
        zoomIn,
        zoomOut,
        onNodeClick,
        onNodeDblClick,
    }
}
