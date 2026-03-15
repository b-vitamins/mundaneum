<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '@/components/AppShell.vue'
import {
  catalogListPageModels,
  type CatalogEntityKey,
  type CatalogListCard,
  type CatalogSortField,
  type CatalogSortOrder,
} from '@/catalog/entityPageModels'

const props = defineProps<{
  entity: CatalogEntityKey
}>()

const route = useRoute()
const router = useRouter()
const model = computed(() => catalogListPageModels[props.entity])

function isSortField(value: unknown): value is CatalogSortField {
  return value === 'name' || value === 'entry_count'
}

function isSortOrder(value: unknown): value is CatalogSortOrder {
  return value === 'asc' || value === 'desc'
}

const items = ref<CatalogListCard[]>([])
const loading = ref(true)
const error = ref('')
const sortBy = ref<CatalogSortField>(
  isSortField(route.query.sort) ? route.query.sort : model.value.defaultSort.field
)
const sortOrder = ref<CatalogSortOrder>(
  isSortOrder(route.query.order) ? route.query.order : model.value.defaultSort.defaultOrder
)
const category = ref<string | undefined>(
  typeof route.query.category === 'string' ? route.query.category : undefined
)

async function loadItems() {
  loading.value = true
  error.value = ''
  try {
    items.value = await model.value.loadItems({
      sortBy: sortBy.value,
      sortOrder: sortOrder.value,
      category: category.value,
    })
  } catch (loadError) {
    console.error(`Failed to load ${props.entity}:`, loadError)
    error.value = `Failed to load ${model.value.title.toLowerCase()}`
  } finally {
    loading.value = false
  }
}

function syncRoute() {
  const query: Record<string, string> = {}
  if (model.value.sortOptions.length > 0) {
    query.sort = sortBy.value
    query.order = sortOrder.value
  }
  if (category.value) {
    query.category = category.value
  }
  router.replace({ query })
}

function changeSort(field: CatalogSortField) {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    const option = model.value.sortOptions.find(candidate => candidate.field === field)
    sortBy.value = field
    sortOrder.value = option?.defaultOrder ?? model.value.defaultSort.defaultOrder
  }
  syncRoute()
  loadItems()
}

function changeCategory(value?: string) {
  category.value = value
  syncRoute()
  loadItems()
}

const subjectGroups = computed(() => model.value.groupItems?.(items.value) ?? [])

onMounted(loadItems)

watch(
  () => props.entity,
  () => {
    sortBy.value = model.value.defaultSort.field
    sortOrder.value = model.value.defaultSort.defaultOrder
    category.value = undefined
    loadItems()
  }
)
</script>

<template>
  <AppShell :title="model.title" :show-search="true">
    <template #actions>
      <span v-if="!loading" class="count">{{ model.countLabel(items) }}</span>
    </template>

    <div v-if="model.categoryOptions || model.sortOptions.length > 0" class="controls">
      <div v-if="model.categoryOptions" class="segmented">
        <button
          v-for="option in model.categoryOptions"
          :key="option.label"
          :class="['segmented-item', { active: category === option.value }]"
          @click="changeCategory(option.value)"
        >
          {{ option.label }}
        </button>
      </div>

      <div v-if="model.sortOptions.length > 0" class="segmented">
        <button
          v-for="option in model.sortOptions"
          :key="option.field"
          :class="['segmented-item', { active: sortBy === option.field }]"
          @click="changeSort(option.field)"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <p v-if="model.helperText" class="helper-text">{{ model.helperText }}</p>

    <div v-if="loading" class="status">
      <span class="spinner"></span>
      {{ model.loadingLabel }}
    </div>
    <div v-else-if="error" class="status error">{{ error }}</div>
    <div v-else-if="items.length === 0" class="status">{{ model.emptyLabel }}</div>

    <div v-else-if="subjectGroups.length > 0" class="subjects-hierarchy">
      <section
        v-for="group in subjectGroups"
        :key="group.title"
        class="category-section card"
      >
        <h2 class="category-header">
          <span class="category-icon">{{ group.icon }}</span>
          <span class="category-name">{{ group.title }}</span>
          <span class="badge badge-muted">{{ group.entryCount }}</span>
        </h2>

        <div class="subareas">
          <router-link
            v-for="item in group.items"
            :key="item.id"
            :to="item.href"
            class="subarea-item"
          >
            <span class="subarea-name">{{ item.title }}</span>
            <span class="subarea-count badge badge-accent">{{ item.countLabel }}</span>
          </router-link>
        </div>
      </section>
    </div>

    <div v-else class="entity-grid">
      <router-link
        v-for="item in items"
        :key="item.href"
        :to="item.href"
        class="entity-card card card-hoverable"
      >
        <div class="entity-card-body">
          <span class="entity-name">{{ item.title }}</span>
          <span v-if="item.badge" class="badge badge-muted">
            {{ item.badge }}
          </span>
        </div>
        <span class="entity-count badge badge-muted">{{ item.countLabel }}</span>
      </router-link>
    </div>
  </AppShell>
</template>

<style scoped>
.count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.controls {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}

.helper-text {
  margin-bottom: var(--space-5);
  color: var(--text-muted);
  font-size: var(--text-sm);
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

.status.error {
  color: var(--danger);
}

.entity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-3);
}

.entity-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-decoration: none;
  color: inherit;
}

.entity-card:hover {
  text-decoration: none;
}

.entity-card-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.entity-name {
  font-weight: 500;
  color: var(--text);
  font-size: var(--text-sm);
}

.entity-count {
  flex-shrink: 0;
}

.subjects-hierarchy {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.category-section {
  padding: 0;
  overflow: hidden;
}

.category-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  margin: 0;
  font-size: var(--text-base);
  font-weight: 600;
  border-bottom: 1px solid var(--border-subtle);
}

.category-icon {
  font-size: 1.25rem;
}

.category-name {
  flex: 1;
  color: var(--text);
}

.subareas {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
}

.subarea-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  color: inherit;
  text-decoration: none;
  transition: background var(--duration-fast) var(--ease-out);
  border-bottom: 1px solid var(--border-subtle);
}

.subarea-item:hover {
  background: var(--accent-subtle);
  text-decoration: none;
}

.subarea-name {
  font-weight: 500;
  color: var(--text);
  font-size: var(--text-sm);
}

.subarea-count {
  font-size: var(--text-xs);
}
</style>
