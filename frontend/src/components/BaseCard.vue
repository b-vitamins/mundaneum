<script setup lang="ts">
/**
 * BaseCard — Composable card with hover lift and consistent styling.
 */
defineProps<{
  hoverable?: boolean
}>()
</script>

<template>
  <div :class="['base-card', { 'card-hoverable': hoverable }]">
    <slot />
  </div>
</template>

<style scoped>
.base-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  transition: all var(--duration-normal) var(--ease-out);
}

.card-hoverable {
  cursor: pointer;
}
.card-hoverable:hover {
  border-color: var(--border);
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
</style>
