import type { CatalogListCard, SubjectGroup } from '@/catalog/types'

const subjectIcons: Record<string, string> = {
    Physics: '⚛️',
    'Computer Science': '💻',
    Mathematics: '📐',
    Programming: '🖥️',
    Statistics: '📊',
    Biology: '🧬',
    Chemistry: '🧪',
    Economics: '📈',
    Engineering: '⚙️',
    Neuroscience: '🧠',
    Philosophy: '🤔',
    Design: '🎨',
    Environment: '🌱',
    Other: '📚',
}

function sortGroupTitles(left: string, right: string): number {
    if (left === 'Other') return 1
    if (right === 'Other') return -1
    return left.localeCompare(right)
}

export function groupSubjectCards(items: CatalogListCard[]): SubjectGroup[] {
    const groups = new Map<string, CatalogListCard[]>()

    for (const item of items) {
        const title = item.groupTitle ?? 'Other'
        const existing = groups.get(title) ?? []
        existing.push(item)
        groups.set(title, existing)
    }

    return Array.from(groups.entries())
        .sort(([left], [right]) => sortGroupTitles(left, right))
        .map(([title, groupItems]) => ({
            title,
            icon: subjectIcons[title] ?? '📁',
            entryCount: groupItems.reduce((sum, subject) => sum + subject.count, 0),
            items: [...groupItems].sort((left, right) => right.count - left.count),
        }))
}
