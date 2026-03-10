<script setup lang="ts">
import type { ViewMode } from '@/graph/types'

defineProps<{
  depth: number
  maxNodes: number
  viewMode: ViewMode
}>()

const emit = defineEmits<{
  (event: 'back'): void
  (event: 'reset'): void
  (event: 'zoom-in'): void
  (event: 'zoom-out'): void
  (event: 'update:depth', value: number): void
  (event: 'update:maxNodes', value: number): void
  (event: 'update:viewMode', value: ViewMode): void
}>()
</script>

<template>
  <header class="toolbar">
    <div class="toolbar-left">
      <router-link to="/" class="brand">Mundaneum</router-link>
      <button class="back-btn" @click="emit('back')">← Back</button>
      <span class="divider">|</span>
      <span class="toolbar-title">Citation Graph</span>
    </div>

    <div class="toolbar-controls">
      <div class="control-group">
        <label class="control-label">Depth</label>
        <div class="toggle-group">
          <button
            :class="['toggle-btn', { active: depth === 1 }]"
            @click="emit('update:depth', 1)"
          >1-hop</button>
          <button
            :class="['toggle-btn', { active: depth === 2 }]"
            @click="emit('update:depth', 2)"
          >2-hop</button>
        </div>
      </div>

      <div class="control-group">
        <label class="control-label">View</label>
        <div class="toggle-group">
          <button
            :class="['toggle-btn', { active: viewMode === 'citation' }]"
            @click="emit('update:viewMode', 'citation')"
          >Citation</button>
          <button
            :class="['toggle-btn', { active: viewMode === 'similarity' }]"
            @click="emit('update:viewMode', 'similarity')"
          >Similarity</button>
        </div>
      </div>

      <div class="control-group">
        <label class="control-label">Nodes: {{ maxNodes }}</label>
        <input
          :value="maxNodes"
          type="range"
          min="10"
          max="200"
          step="5"
          class="range-slider"
          @input="emit('update:maxNodes', Number(($event.target as HTMLInputElement).value))"
        />
      </div>

      <button class="icon-btn" title="Reset view (R)" @click="emit('reset')">⟳</button>
      <button class="icon-btn" title="Zoom in (+)" @click="emit('zoom-in')">+</button>
      <button class="icon-btn" title="Zoom out (-)" @click="emit('zoom-out')">−</button>
    </div>
  </header>
</template>
