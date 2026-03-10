<script setup lang="ts">
import type { GraphNode } from '@/api/client'

defineProps<{
  formatAuthors: (authors: string[]) => string
  node: GraphNode
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'go-to-entry', id: string): void
  (event: 'open-on-s2', id: string): void
  (event: 'recenter', node: GraphNode): void
}>()
</script>

<template>
  <aside class="detail-panel">
    <div class="panel-header">
      <h3 class="panel-title">Paper Details</h3>
      <button class="close-btn" @click="emit('close')">✕</button>
    </div>

    <div class="panel-content">
      <h2 class="paper-title">{{ node.title }}</h2>

      <p class="paper-authors">{{ formatAuthors(node.authors) }}</p>

      <div class="paper-meta">
        <span v-if="node.venue" class="meta-tag">{{ node.venue }}</span>
        <span v-if="node.year" class="meta-tag">{{ node.year }}</span>
        <span class="meta-tag">{{ node.citation_count.toLocaleString() }} citations</span>
      </div>

      <div v-if="node.fields_of_study?.length" class="fields">
        <span
          v-for="field in node.fields_of_study"
          :key="field"
          class="field-tag"
        >{{ field }}</span>
      </div>

      <div class="panel-actions">
        <button
          v-if="node.in_library && node.entry_id"
          class="action-btn primary"
          @click="emit('go-to-entry', node.entry_id)"
        >View in Mundaneum</button>

        <button
          v-if="node.in_library && node.entry_id"
          class="action-btn"
          @click="emit('recenter', node)"
        >Re-center Graph</button>

        <button
          class="action-btn"
          @click="emit('open-on-s2', node.id)"
        >Open on Semantic Scholar ↗</button>
      </div>

      <div v-if="node.in_library" class="library-badge">
        <span class="badge-icon">📚</span>
        <span>This paper is in your library</span>
      </div>
    </div>
  </aside>
</template>
