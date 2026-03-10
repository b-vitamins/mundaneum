<script setup lang="ts">
import type { YearHistogramItem } from '@/graph/data'

defineProps<{
  filterKeyword: string
  filterYearMax: number
  filterYearMin: number
  maxHistCount: number
  yearHistogram: YearHistogramItem[]
  yearMax: number
  yearMin: number
}>()

const emit = defineEmits<{
  (event: 'update:filterKeyword', value: string): void
  (event: 'update:filterYearMin', value: number): void
  (event: 'update:filterYearMax', value: number): void
}>()
</script>

<template>
  <div class="filter-bar">
    <div class="filter-group filter-year">
      <label class="filter-label">Year: {{ filterYearMin }}–{{ filterYearMax }}</label>
      <div class="year-slider-container">
        <div class="year-histogram">
          <div
            v-for="h in yearHistogram"
            :key="h.year"
            class="hist-bar"
            :style="{
              height: (h.count / maxHistCount) * 100 + '%',
              opacity: h.year >= filterYearMin && h.year <= filterYearMax ? 1 : 0.2
            }"
            :title="`${h.year}: ${h.count} papers`"
          ></div>
        </div>
        <div class="dual-range">
          <input
            :value="filterYearMin"
            type="range"
            :min="yearMin"
            :max="yearMax"
            class="range-min"
            @input="emit('update:filterYearMin', Number(($event.target as HTMLInputElement).value))"
          />
          <input
            :value="filterYearMax"
            type="range"
            :min="yearMin"
            :max="yearMax"
            class="range-max"
            @input="emit('update:filterYearMax', Number(($event.target as HTMLInputElement).value))"
          />
        </div>
      </div>
    </div>

    <div class="filter-group filter-keyword">
      <input
        :value="filterKeyword"
        type="text"
        placeholder="Filter by keyword…"
        class="keyword-input"
        @input="emit('update:filterKeyword', ($event.target as HTMLInputElement).value)"
      />
    </div>
  </div>
</template>
