<script setup lang="ts">
import type { GraphExplorerTab } from '@/features/graph/types'

defineProps<{
  activeTab: GraphExplorerTab
  priorCount: number
  derivativeCount: number
}>()

const emit = defineEmits<{
  (event: 'update:activeTab', value: GraphExplorerTab): void
}>()
</script>

<template>
  <nav class="view-tabs">
    <button
      :class="['view-tab', { active: activeTab === 'graph' }]"
      @click="emit('update:activeTab', 'graph')"
    >◉ Graph</button>
    <button
      :class="['view-tab', { active: activeTab === 'prior' }]"
      @click="emit('update:activeTab', 'prior')"
    >
      Prior Works
      <span v-if="priorCount" class="tab-count">{{ priorCount }}</span>
    </button>
    <button
      :class="['view-tab', { active: activeTab === 'derivative' }]"
      @click="emit('update:activeTab', 'derivative')"
    >
      Derivative Works
      <span v-if="derivativeCount" class="tab-count">{{ derivativeCount }}</span>
    </button>
  </nav>
</template>
