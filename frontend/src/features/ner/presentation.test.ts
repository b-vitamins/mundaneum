import { describe, expect, it } from 'vitest'

import { nerLabelColor, parseNodeKey } from '@/features/ner/presentation'

describe('NER presentation helpers', () => {
    it('maps known labels to stable colors and falls back for unknown labels', () => {
        expect(nerLabelColor('method')).toBe('#3b82f6')
        expect(nerLabelColor('unknown-label')).toBe('#94a3b8')
    })

    it('parses node keys into label and canonical id', () => {
        expect(parseNodeKey('task|ent123')).toEqual({
            label: 'task',
            canonicalId: 'ent123',
        })
        expect(parseNodeKey('invalid-node-key')).toBeNull()
        expect(parseNodeKey('task|')).toBeNull()
    })
})
