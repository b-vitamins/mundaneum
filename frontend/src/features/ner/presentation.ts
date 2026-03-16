export const NER_LABEL_COLORS: Record<string, string> = {
    method: '#3b82f6',
    'model-family': '#8b5cf6',
    dataset: '#22c55e',
    task: '#f59e0b',
    metric: '#14b8a6',
    'architecture-component': '#6366f1',
    'training-strategy': '#f43f5e',
    'theory-construct': '#64748b',
    paradigm: '#ec4899',
    'problem-setting': '#f97316',
    'property-focus': '#06b6d4',
    regularization: '#84cc16',
}

const DEFAULT_NER_LABEL_COLOR = '#94a3b8'

export function nerLabelColor(label: string): string {
    return NER_LABEL_COLORS[label] ?? DEFAULT_NER_LABEL_COLOR
}

export interface ParsedNodeKey {
    label: string
    canonicalId: string
}

export function parseNodeKey(nodeKey: string): ParsedNodeKey | null {
    const [label, ...rest] = nodeKey.split('|')
    const canonicalId = rest.join('|')
    if (!label || !canonicalId) {
        return null
    }
    return { label, canonicalId }
}
