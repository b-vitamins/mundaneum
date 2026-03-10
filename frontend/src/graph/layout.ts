import type { GraphLayout, SimEdge, SimNode } from '@/graph/types'

interface QuadNode {
  x: number
  y: number
  mass: number
  children: (QuadNode | null)[]
  body: SimNode | null
  isLeaf: boolean
  cx: number
  cy: number
  size: number
}

function createQuad(x: number, y: number, size: number): QuadNode {
  return {
    x,
    y,
    size,
    mass: 0,
    cx: 0,
    cy: 0,
    children: [null, null, null, null],
    body: null,
    isLeaf: true,
  }
}

function insertIntoChild(quad: QuadNode, node: SimNode): void {
  const halfSize = quad.size / 2
  const midX = quad.x + halfSize
  const midY = quad.y + halfSize

  let index: number
  if (node.x < midX) {
    index = node.y < midY ? 0 : 2
  } else {
    index = node.y < midY ? 1 : 3
  }

  if (!quad.children[index]) {
    const childX = index % 2 === 0 ? quad.x : midX
    const childY = index < 2 ? quad.y : midY
    quad.children[index] = createQuad(childX, childY, halfSize)
  }

  insertNode(quad.children[index]!, node)
}

function insertNode(quad: QuadNode, node: SimNode): void {
  if (quad.mass === 0 && quad.isLeaf) {
    quad.body = node
    quad.mass = 1
    quad.cx = node.x
    quad.cy = node.y
    return
  }

  if (quad.isLeaf && quad.body) {
    const existing = quad.body
    quad.body = null
    quad.isLeaf = false
    insertIntoChild(quad, existing)
  }

  const totalMass = quad.mass + 1
  quad.cx = (quad.cx * quad.mass + node.x) / totalMass
  quad.cy = (quad.cy * quad.mass + node.y) / totalMass
  quad.mass = totalMass
  insertIntoChild(quad, node)
}

function buildQuadtree(nodes: SimNode[]): QuadNode | null {
  if (nodes.length === 0) {
    return null
  }

  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity

  for (const node of nodes) {
    if (node.x < minX) minX = node.x
    if (node.x > maxX) maxX = node.x
    if (node.y < minY) minY = node.y
    if (node.y > maxY) maxY = node.y
  }

  const pad = 10
  const size = Math.max(maxX - minX, maxY - minY) + pad * 2
  const root = createQuad(minX - pad, minY - pad, size)
  for (const node of nodes) {
    insertNode(root, node)
  }
  return root
}

function computeRepulsion(
  node: SimNode,
  quad: QuadNode | null,
  theta: number,
  strength: number
): void {
  if (!quad || quad.mass === 0) {
    return
  }

  const dx = quad.cx - node.x
  const dy = quad.cy - node.y
  const dist = Math.sqrt(dx * dx + dy * dy) || 1

  if (quad.size / dist < theta || quad.isLeaf) {
    if (quad.body === node) {
      return
    }
    const force = -strength * quad.mass / (dist * dist)
    node.vx += force * dx / dist
    node.vy += force * dy / dist
    return
  }

  for (const child of quad.children) {
    if (child) {
      computeRepulsion(node, child, theta, strength)
    }
  }
}

export class ForceLayout implements GraphLayout {
  private nodes: SimNode[] = []
  private edges: SimEdge[] = []
  private alpha = 1.0
  private alphaDecay = 0.02
  private alphaMin = 0.001
  private repulsionStrength = 300
  private springStrength = 0.05
  private baseSpringLength = 120
  private centerStrength = 0.01
  private damping = 0.85
  private theta = 0.9
  private isSimilarityMode = false

  init(nodes: SimNode[], edges: SimEdge[]): void {
    this.nodes = nodes
    this.edges = edges
    this.alpha = 1.0
    this.isSimilarityMode = edges.some((edge) => edge.weight !== undefined && edge.weight > 0)

    if (this.isSimilarityMode) {
      this.repulsionStrength = 150
      this.springStrength = 0.08
      this.baseSpringLength = 80
      this.centerStrength = 0.005
    } else {
      this.repulsionStrength = 300
      this.springStrength = 0.05
      this.baseSpringLength = 120
      this.centerStrength = 0.01
    }

    const count = nodes.length
    for (let index = 0; index < count; index += 1) {
      const angle = (2 * Math.PI * index) / count
      const radius = Math.sqrt(count) * 30
      nodes[index].x = Math.cos(angle) * radius
      nodes[index].y = Math.sin(angle) * radius
      nodes[index].vx = 0
      nodes[index].vy = 0
    }
  }

  tick(_dt: number): boolean {
    if (this.alpha < this.alphaMin) {
      return true
    }

    const tree = buildQuadtree(this.nodes)
    for (const node of this.nodes) {
      computeRepulsion(node, tree, this.theta, this.repulsionStrength * this.alpha)
    }

    for (const edge of this.edges) {
      const dx = edge.target.x - edge.source.x
      const dy = edge.target.y - edge.source.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1

      let targetDist = this.baseSpringLength
      let strength = this.springStrength
      if (this.isSimilarityMode && edge.weight !== undefined) {
        targetDist = (1 - edge.weight) * 200 + 40
        strength = this.springStrength * (0.5 + edge.weight)
      }

      const force = (dist - targetDist) * strength * this.alpha
      const fx = force * dx / dist
      const fy = force * dy / dist
      edge.source.vx += fx
      edge.source.vy += fy
      edge.target.vx -= fx
      edge.target.vy -= fy
    }

    for (const node of this.nodes) {
      node.vx -= node.x * this.centerStrength * this.alpha
      node.vy -= node.y * this.centerStrength * this.alpha
    }

    for (const node of this.nodes) {
      node.vx *= this.damping
      node.vy *= this.damping
      node.x += node.vx
      node.y += node.vy
    }

    this.alpha *= 1 - this.alphaDecay
    return false
  }

  destroy(): void {
    this.nodes = []
    this.edges = []
  }
}
