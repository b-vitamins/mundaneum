<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import {
  catalogDetailPageModels,
  type CatalogDetailItem,
  type CatalogEntityKey,
  type CatalogEntryItem,
} from '@/catalog/entityPageModels'

const props = defineProps<{
  entity: CatalogEntityKey
}>()

const route = useRoute()
const model = computed(() => catalogDetailPageModels[props.entity])

const detail = ref<CatalogDetailItem | null>(null)
const entries = ref<CatalogEntryItem[]>([])
const loading = ref(true)
const error = ref('')

function routeValue(): string {
  return route.params[model.value.routeParam] as string
}

async function loadPage() {
  const value = routeValue()
  loading.value = true
  error.value = ''
  try {
    const [detailData, entryData] = await Promise.all([
      model.value.loadDetail(value),
      model.value.loadEntries(value),
    ])
    detail.value = detailData
    entries.value = entryData
  } catch (loadError) {
    console.error(`Failed to load ${props.entity} detail:`, loadError)
    error.value = model.value.notFoundLabel
  } finally {
    loading.value = false
  }
}

const title = computed(() => detail.value ? model.value.title(detail.value) : model.value.titleFallback)
const statsLabel = computed(() => detail.value ? model.value.statsLabel(detail.value) : '')
const badge = computed(() => detail.value ? model.value.badge?.(detail.value) ?? null : null)
const secondaryLines = computed(() => detail.value ? model.value.secondaryLines?.(detail.value) ?? [] : [])

onMounted(loadPage)
watch(
  () => route.params[model.value.routeParam],
  loadPage,
)
</script>

<template>
  <AppShell :back-to="model.backTo" :back-label="model.backLabel" :title="title">
    <div v-if="loading" class="status">
      <span class="spinner"></span>
      {{ model.loadingLabel }}
    </div>
    <div v-else-if="error" class="status error">{{ error }}</div>

    <div v-else-if="detail" class="detail-content">
      <div class="detail-header">
        <div class="title-row">
          <h1 class="detail-name">{{ title }}</h1>
          <span v-if="badge" class="badge badge-muted">{{ badge }}</span>
        </div>
        <p v-for="line in secondaryLines" :key="line" class="detail-secondary">{{ line }}</p>
        <p class="detail-stats">{{ statsLabel }}</p>
      </div>

      <section>
        <h2 class="section-title">{{ model.sectionTitle }}</h2>
        <div v-if="entries.length === 0" class="empty">{{ model.emptyLabel }}</div>
        <div v-else class="entries-list">
          <router-link
            v-for="entry in entries"
            :key="entry.id"
            :to="`/entry/${entry.id}`"
            class="entry-row card card-hoverable"
          >
            <div class="entry-body">
              <h3 class="entry-title">{{ entry.title }}</h3>
              <p class="entry-meta">
                <span
                  v-for="meta in model.entryMeta(entry)"
                  :key="`${entry.id}-${meta}`"
                  :class="meta === entry.entry_type ? 'badge badge-muted' : ''"
                >
                  {{ meta }}
                </span>
              </p>
            </div>
            <span v-if="entry.read" class="badge badge-success">✓ Read</span>
          </router-link>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.status {
  text-align: center;
  padding: var(--space-12);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

.status.error {
  color: var(--danger);
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.detail-header {
  padding-bottom: var(--space-6);
  border-bottom: 1px solid var(--border-subtle);
}

.title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.detail-name {
  font-size: var(--text-2xl);
  font-weight: 600;
}

.detail-secondary {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-1);
}

.detail-stats {
  color: var(--text-muted);
  font-size: var(--text-base);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: 600;
  margin-bottom: var(--space-4);
}

.empty {
  color: var(--text-muted);
  padding: var(--space-8);
  text-align: center;
}

.entries-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.entry-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  text-decoration: none;
  color: inherit;
}

.entry-row:hover {
  text-decoration: none;
}

.entry-body {
  flex: 1;
  min-width: 0;
}

.entry-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text);
  margin-bottom: var(--space-1);
}

.entry-meta {
  display: flex;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
  align-items: center;
  flex-wrap: wrap;
}
</style>
