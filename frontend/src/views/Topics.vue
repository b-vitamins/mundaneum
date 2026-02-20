<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type TopicListItem } from '@/api/client'
import AppShell from '@/components/AppShell.vue'

const route = useRoute()
const router = useRouter()

const topics = ref<TopicListItem[]>([])
const loading = ref(true)
const error = ref('')

type SortField = 'name' | 'entry_count'
type SortOrder = 'asc' | 'desc'

const sortBy = ref<SortField>((route.query.sort as SortField) || 'name')
const sortOrder = ref<SortOrder>((route.query.order as SortOrder) || 'asc')

async function loadTopics() {
  loading.value = true
  error.value = ''
  try {
    topics.value = await api.listTopics(200, 0, sortBy.value, sortOrder.value)
  } catch (e) {
    console.error('Failed to load topics:', e)
    error.value = 'Failed to load topics'
  } finally {
    loading.value = false
  }
}

function changeSort(field: SortField) {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = field === 'entry_count' ? 'desc' : 'asc'
  }
  router.replace({ query: { ...route.query, sort: sortBy.value, order: sortOrder.value } })
  loadTopics()
}

onMounted(loadTopics)
</script>

<template>
  <AppShell title="Topics" :show-search="true">
    <template #actions>
      <span class="count">{{ topics.length }} topics</span>
    </template>

    <div class="controls">
      <div class="segmented">
        <button
          :class="['segmented-item', { active: sortBy === 'name' }]"
          @click="changeSort('name')"
        >Name</button>
        <button
          :class="['segmented-item', { active: sortBy === 'entry_count' }]"
          @click="changeSort('entry_count')"
        >Entry Count</button>
      </div>
    </div>

    <div v-if="loading" class="status">
      <span class="spinner"></span>
      Loading topics...
    </div>
    <div v-else-if="error" class="status error">{{ error }}</div>
    <div v-else-if="topics.length === 0" class="status">No topics found.</div>

    <div v-else class="topics-grid">
      <router-link
        v-for="topic in topics"
        :key="topic.id"
        :to="`/topics/${topic.slug}`"
        class="topic-card card card-hoverable"
      >
        <span class="topic-name">{{ topic.name }}</span>
        <span class="topic-count badge badge-muted">{{ topic.entry_count }}</span>
      </router-link>
    </div>
  </AppShell>
</template>

<style scoped>
.count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}
.controls { margin-bottom: var(--space-5); }
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
.topics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-3);
}
.topic-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  text-decoration: none;
  color: inherit;
}
.topic-card:hover { text-decoration: none; }
.topic-name {
  font-weight: 500;
  color: var(--text);
  font-size: var(--text-sm);
}
</style>
