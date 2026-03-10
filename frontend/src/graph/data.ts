import type { GraphData, GraphNode } from '@/api/client'

export interface YearHistogramItem {
  year: number
  count: number
}

export function sliceGraphData(data: GraphData, nodeCount: number): GraphData {
  const centerNode = data.nodes.find((node) => node.id === data.center_id)
  const otherNodes = data.nodes.filter((node) => node.id !== data.center_id)
  const nodes = centerNode
    ? [centerNode, ...otherNodes.slice(0, nodeCount - 1)]
    : otherNodes.slice(0, nodeCount)
  const nodeIds = new Set(nodes.map((node) => node.id))

  return {
    ...data,
    nodes,
    edges: data.edges.filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)),
    similarity_edges: data.similarity_edges.filter(
      (edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target)
    ),
  }
}

export function getYearBounds(data: GraphData): { min: number; max: number } | null {
  const years = data.nodes
    .map((node) => node.year)
    .filter((year): year is number => typeof year === 'number')

  if (years.length === 0) {
    return null
  }

  return {
    min: Math.min(...years),
    max: Math.max(...years),
  }
}

export function buildYearHistogram(
  data: GraphData | null,
  yearMin: number,
  yearMax: number
): YearHistogramItem[] {
  if (!data) {
    return []
  }

  const counts: Record<number, number> = {}
  for (const node of data.nodes) {
    if (node.year) {
      counts[node.year] = (counts[node.year] || 0) + 1
    }
  }

  const histogram: YearHistogramItem[] = []
  for (let year = yearMin; year <= yearMax; year += 1) {
    histogram.push({ year, count: counts[year] || 0 })
  }
  return histogram
}

export function matchesGraphFilter(
  node: GraphNode,
  keyword: string,
  yearMin: number,
  yearMax: number
): boolean {
  if (node.year && (node.year < yearMin || node.year > yearMax)) {
    return false
  }

  if (!keyword) {
    return true
  }

  const text = [node.title, ...node.authors, node.venue || ''].join(' ').toLowerCase()
  return text.includes(keyword)
}

export function formatGraphAuthors(authors: string[]): string {
  if (authors.length <= 3) {
    return authors.join(', ')
  }
  return `${authors.slice(0, 3).join(', ')} +${authors.length - 3}`
}

export function formatGraphCount(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`
  return value.toString()
}
