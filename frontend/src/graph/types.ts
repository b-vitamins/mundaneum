import type { GraphData, GraphNode } from '@/api/client'

export interface SimNode {
  id: string
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  data: GraphNode
}

export interface SimEdge {
  source: SimNode
  target: SimNode
  is_influential: boolean
  weight?: number
}

export interface Camera {
  x: number
  y: number
  zoom: number
}

export interface RenderState {
  centerId: string
  hoveredId: string | null
  selectedId: string | null
  isDark: boolean
  viewMode: ViewMode
  filteredIds: Set<string> | null
}

export interface GraphLayout {
  init(nodes: SimNode[], edges: SimEdge[]): void
  tick(dt: number): boolean
  destroy(): void
}

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

export type ViewMode = 'citation' | 'similarity'

export function buildSimNodes(data: GraphData): {
  centerId: string
  nodeMap: Map<string, SimNode>
  simNodes: SimNode[]
} {
  const nodeMap = new Map<string, SimNode>()
  const simNodes = data.nodes.map((node) => {
    const radius = 4 + 2 * Math.log2(Math.max(1, node.citation_count))
    const simNode: SimNode = {
      id: node.id,
      x: 0,
      y: 0,
      vx: 0,
      vy: 0,
      radius: Math.min(radius, 25),
      data: node,
    }
    nodeMap.set(node.id, simNode)
    return simNode
  })

  const centerId = data.center_id
  const centerNode = nodeMap.get(centerId)
  if (centerNode) {
    centerNode.x = 0
    centerNode.y = 0
  }

  return { centerId, nodeMap, simNodes }
}

export function buildSimEdges(
  data: GraphData,
  nodeMap: Map<string, SimNode>,
  mode: ViewMode
): SimEdge[] {
  if (mode === 'citation') {
    return data.edges.flatMap((edge) => {
      const source = nodeMap.get(edge.source)
      const target = nodeMap.get(edge.target)
      if (!source || !target) {
        return []
      }
      return [{
        source,
        target,
        is_influential: edge.is_influential,
      }]
    })
  }

  return data.similarity_edges.flatMap((edge) => {
    const source = nodeMap.get(edge.source)
    const target = nodeMap.get(edge.target)
    if (!source || !target) {
      return []
    }
    return [{
      source,
      target,
      is_influential: false,
      weight: edge.weight,
    }]
  })
}
