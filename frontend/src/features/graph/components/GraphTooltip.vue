<script setup lang="ts">
import type { GraphNode } from '@/api/client'

defineProps<{
  node: GraphNode
}>()
</script>

<template>
  <div class="tooltip">
    <div class="tooltip-title">{{ node.title }}</div>
    <div class="tooltip-meta">
      <span v-if="node.venue">{{ node.venue }}</span>
      <span v-if="node.year">{{ node.year }}</span>
      <span>{{ node.citation_count }} citations</span>
    </div>
    <div v-if="node.in_library" class="tooltip-badge">📚 In your library</div>
  </div>
</template>
