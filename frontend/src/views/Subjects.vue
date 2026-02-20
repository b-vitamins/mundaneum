<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api, type SubjectListItem } from '@/api/client'
import AppShell from '@/components/AppShell.vue'

const subjects = ref<SubjectListItem[]>([])
const loading = ref(true)
const error = ref('')

async function loadSubjects() {
  loading.value = true
  error.value = ''
  try {
    subjects.value = await api.listSubjects(200, 0, 'name', 'asc')
  } catch (e) {
    console.error('Failed to load subjects:', e)
    error.value = 'Failed to load subjects'
  } finally {
    loading.value = false
  }
}

const groupedSubjects = computed(() => {
  const groups: Record<string, SubjectListItem[]> = {}
  for (const subject of subjects.value) {
    const parent = subject.parent_slug || 'other'
    const parentDisplay = parent.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
    if (!groups[parentDisplay]) groups[parentDisplay] = []
    groups[parentDisplay].push(subject)
  }
  const sortedKeys = Object.keys(groups).sort((a, b) => {
    if (a === 'Other') return 1
    if (b === 'Other') return -1
    return a.localeCompare(b)
  })
  const result: Record<string, SubjectListItem[]> = {}
  for (const key of sortedKeys) {
    result[key] = groups[key].sort((a, b) => b.entry_count - a.entry_count)
  }
  return result
})

const categoryIcons: Record<string, string> = {
  'Physics': '⚛️', 'Computer Science': '💻', 'Mathematics': '📐',
  'Programming': '🖥️', 'Statistics': '📊', 'Biology': '🧬',
  'Chemistry': '🧪', 'Economics': '📈', 'Engineering': '⚙️',
  'Neuroscience': '🧠', 'Philosophy': '🤔', 'Design': '🎨',
  'Environment': '🌱', 'Other': '📚',
}
function getIcon(category: string): string { return categoryIcons[category] || '📁' }
function getCategoryEntryCount(children: SubjectListItem[]): number {
  return children.reduce((sum, s) => sum + s.entry_count, 0)
}

onMounted(loadSubjects)
</script>

<template>
  <AppShell title="Subject Areas" :show-search="true">
    <div v-if="loading" class="status">
      <span class="spinner"></span>
      Loading subjects...
    </div>
    <div v-else-if="error" class="status error">{{ error }}</div>
    <div v-else-if="subjects.length === 0" class="status">No subjects found.</div>

    <div v-else class="subjects-hierarchy">
      <section
        v-for="(children, category) in groupedSubjects"
        :key="category"
        class="category-section card"
      >
        <h2 class="category-header">
          <span class="category-icon">{{ getIcon(category as string) }}</span>
          <span class="category-name">{{ category }}</span>
          <span class="badge badge-muted">{{ getCategoryEntryCount(children) }}</span>
        </h2>

        <div class="subareas">
          <router-link
            v-for="subject in children"
            :key="subject.id"
            :to="`/subjects/${subject.slug}`"
            class="subarea-item"
          >
            <span class="subarea-name">{{ subject.display_name || subject.name }}</span>
            <span class="subarea-count badge badge-accent">{{ subject.entry_count }}</span>
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
.status.error { color: var(--danger); }

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
