import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const root = dirname(fileURLToPath(import.meta.url))

function lineCount(relativePath: string): number {
    return readFileSync(resolve(root, relativePath), 'utf8')
        .trimEnd()
        .split('\n').length
}

describe('frontend architecture guards', () => {
    it('keeps page shells and registries small', () => {
        expect(lineCount('./views/GraphExplorer.vue')).toBeLessThanOrEqual(220)
        expect(lineCount('./views/Search.vue')).toBeLessThanOrEqual(320)
        expect(lineCount('./catalog/entityPageModels.ts')).toBeLessThanOrEqual(60)
    })

    it('keeps state logic out of page shells', () => {
        expect(lineCount('./features/search/useSearchController.ts')).toBeLessThanOrEqual(220)
        expect(lineCount('./features/graph/components/GraphToolbar.vue')).toBeLessThanOrEqual(100)
        expect(lineCount('./features/graph/components/GraphAggregateTable.vue')).toBeLessThanOrEqual(80)
    })
})
