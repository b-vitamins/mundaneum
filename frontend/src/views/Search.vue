<script setup lang="ts">
import AppShell from '@/components/AppShell.vue'
import { useSearchController } from '@/features/search/useSearchController'

const {
  applyFilters,
  clearFilters,
  entryTypes,
  error,
  filters,
  handleSearch,
  partialWarning,
  query,
  results,
  showFilters,
  status,
  total,
  unavailableDetail,
  viewState,
} = useSearchController()
</script>

<template>
  <AppShell title="Search">
    <template #actions>
      <button class="btn btn-ghost" @click="showFilters = !showFilters">
        {{ showFilters ? 'Hide Filters' : 'Filters' }}
      </button>
    </template>

    <!-- Search bar -->
    <form class="search-bar" @submit.prevent="handleSearch">
      <div class="search-wrapper">
        <span class="search-icon">⌕</span>
        <input
          v-model="query"
          type="text"
          class="search-input input"
          placeholder="Search papers, authors, topics..."
          autofocus
        />
      </div>
    </form>

    <div class="search-layout">
      <!-- Filters panel -->
      <aside v-if="showFilters" class="filters card">
        <div class="filter-group">
          <label class="filter-label">Type</label>
          <select v-model="filters.entry_type" class="filter-control input">
            <option value="">All types</option>
            <option v-for="t in entryTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>

        <div class="filter-group">
          <label class="filter-label">Year Range</label>
          <div class="year-range">
            <input v-model.number="filters.year_from" type="number" class="filter-control input" placeholder="From" />
            <span class="year-sep">–</span>
            <input v-model.number="filters.year_to" type="number" class="filter-control input" placeholder="To" />
          </div>
        </div>

        <div class="filter-group">
          <label class="filter-label">PDF</label>
          <select v-model="filters.has_pdf" class="filter-control input">
            <option value="">Any</option>
            <option value="true">Attached</option>
            <option value="false">Missing</option>
          </select>
        </div>

        <div class="filter-group">
          <label class="filter-label">Read status</label>
          <select v-model="filters.read" class="filter-control input">
            <option value="">Any</option>
            <option value="true">Read</option>
            <option value="false">Unread</option>
          </select>
        </div>

        <div class="filter-actions">
          <button type="button" class="btn btn-primary" @click="applyFilters">Apply</button>
          <button type="button" class="btn btn-ghost" @click="clearFilters">Clear</button>
        </div>
      </aside>

      <!-- Results -->
      <section class="results">
        <div class="results-header" v-if="total > 0">
          <span class="results-count">{{ total >= 1000 ? '1,000+' : total.toLocaleString() }} results</span>
        </div>

        <div v-if="status === 'partial' && viewState === 'results'" class="status warning">
          <p>{{ partialWarning || 'Full-text search is unavailable. Showing degraded database results.' }}</p>
        </div>

        <div v-if="viewState === 'loading'" class="status">
          <span class="spinner"></span>
          Searching...
        </div>
        <p v-else-if="viewState === 'error'" class="status error">{{ error }}</p>
        <div v-else-if="viewState === 'unavailable'" class="status error">
          <p>Search is temporarily unavailable.</p>
          <p v-if="unavailableDetail" class="status-detail">{{ unavailableDetail }}</p>
        </div>
        <p v-else-if="viewState === 'empty'" class="status">No results found</p>
        <p v-else-if="viewState === 'idle'" class="status empty-state">Enter a search term to find papers</p>

        <div class="results-list">
          <router-link
            v-for="item in results"
            :key="item.id"
            :to="`/entry/${item.id}`"
            class="result-row card card-hoverable"
          >
            <div class="result-body">
              <h3 class="result-title">{{ item.title }}</h3>
              <p v-if="item.authors.length" class="result-authors">{{ item.authors.join(', ') }}</p>
              <div class="result-meta">
                <span v-if="item.venue">{{ item.venue }}</span>
                <span v-if="item.year">{{ item.year }}</span>
              </div>
            </div>
            <div class="result-badges">
              <span v-if="item.has_pdf" class="badge badge-accent">PDF</span>
              <span v-if="item.read" class="badge badge-success">✓ Read</span>
            </div>
          </router-link>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.search-bar {
  margin-bottom: var(--space-5);
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: var(--space-4);
  font-size: var(--text-lg);
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  padding-left: 2.5rem;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.search-input:focus {
  box-shadow: var(--shadow-md), 0 0 0 3px var(--accent-subtle);
}

.search-layout {
  display: flex;
  gap: var(--space-6);
}

.filters {
  width: 240px;
  flex-shrink: 0;
  height: fit-content;
  position: sticky;
  top: calc(var(--header-height) + var(--space-6));
}

.filter-group {
  margin-bottom: var(--space-4);
}

.filter-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.filter-control {
  font-size: var(--text-sm);
  padding: var(--space-2) var(--space-3);
}

.year-range {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
.year-range .filter-control {
  min-width: 80px;
}
.year-sep {
  color: var(--text-muted);
}

.status.warning {
  color: var(--warning-strong, #8a5a00);
  background: var(--warning-bg, #fff5d6);
  border: 1px solid var(--warning-border, #f0cf72);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
}

.status-detail {
  margin-top: var(--space-1);
  font-size: var(--text-sm);
}

.filter-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-subtle);
}

.results {
  flex: 1;
  min-width: 0;
}

.results-header {
  margin-bottom: var(--space-4);
}

.results-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.status {
  text-align: center;
  padding: var(--space-12);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}
.status.error { color: var(--danger); }

.results-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.result-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  text-decoration: none;
  color: inherit;
}
.result-row:hover { text-decoration: none; }

.result-body {
  flex: 1;
  min-width: 0;
}

.result-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text);
  line-height: var(--leading-tight);
  margin-bottom: var(--space-1);
}

.result-authors {
  font-size: var(--text-sm);
  color: var(--accent);
  margin-bottom: var(--space-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-meta {
  display: flex;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.result-badges {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
  margin-left: var(--space-4);
}
</style>
