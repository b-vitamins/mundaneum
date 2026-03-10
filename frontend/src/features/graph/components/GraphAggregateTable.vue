<script setup lang="ts">
import type { AggregateEntry } from '@/api/client'

defineProps<{
  description: string
  emptyLabel: string
  formatAuthors: (authors: string[]) => string
  formatCount: (value: number) => string
  papers: AggregateEntry[]
  title: string
}>()

const emit = defineEmits<{
  (event: 'select-paper', paper: AggregateEntry): void
}>()
</script>

<template>
  <div class="aggregate-container">
    <div class="aggregate-header">
      <h2 class="aggregate-title">{{ title }}</h2>
      <p class="aggregate-desc">{{ description }}</p>
    </div>
    <div v-if="papers.length === 0" class="aggregate-empty">
      {{ emptyLabel }}
    </div>
    <table v-else class="aggregate-table">
      <thead>
        <tr>
          <th class="th-title">Paper</th>
          <th class="th-num">Year</th>
          <th class="th-num">Citations</th>
          <th class="th-num">Freq</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="paper in papers"
          :key="paper.id"
          class="agg-row"
          :class="{ 'in-library': paper.in_library }"
          @click="emit('select-paper', paper)"
        >
          <td class="td-title">
            <div class="agg-paper-title">{{ paper.title }}</div>
            <div class="agg-paper-authors">{{ formatAuthors(paper.authors) }}</div>
            <div v-if="paper.venue" class="agg-paper-venue">{{ paper.venue }}</div>
          </td>
          <td class="td-num">{{ paper.year || '—' }}</td>
          <td class="td-num">{{ formatCount(paper.citation_count) }}</td>
          <td class="td-num">
            <span class="freq-badge">{{ paper.frequency }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
