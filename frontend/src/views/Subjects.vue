<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api, type SubjectListItem } from '@/api/client'

// State
const subjects = ref<SubjectListItem[]>([])
const loading = ref(true)
const error = ref('')

// Actions
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

// Group subjects by parent category
const groupedSubjects = computed(() => {
  const groups: Record<string, SubjectListItem[]> = {}
  
  for (const subject of subjects.value) {
    const parent = subject.parent_slug || 'other'
    // Convert parent_slug to display name (e.g., "computer-science" -> "Computer Science")
    const parentDisplay = parent.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
    
    if (!groups[parentDisplay]) {
      groups[parentDisplay] = []
    }
    groups[parentDisplay].push(subject)
  }
  
  // Sort groups alphabetically, but put "Other" last
  const sortedKeys = Object.keys(groups).sort((a, b) => {
    if (a === 'Other') return 1
    if (b === 'Other') return -1
    return a.localeCompare(b)
  })
  
  const sortedGroups: Record<string, SubjectListItem[]> = {}
  for (const key of sortedKeys) {
    // Sort children by entry count descending
    sortedGroups[key] = groups[key].sort((a, b) => b.entry_count - a.entry_count)
  }
  
  return sortedGroups
})

// Category icons
const categoryIcons: Record<string, string> = {
  'Physics': '⚛️',
  'Computer Science': '💻',
  'Mathematics': '📐',
  'Programming': '🖥️',
  'Statistics': '📊',
  'Biology': '🧬',
  'Chemistry': '🧪',
  'Economics': '📈',
  'Engineering': '⚙️',
  'Neuroscience': '🧠',
  'Philosophy': '🤔',
  'Other': '📚',
}

function getIcon(category: string): string {
  return categoryIcons[category] || '📁'
}

// Total entries per category
function getCategoryEntryCount(children: SubjectListItem[]): number {
  return children.reduce((sum, s) => sum + s.entry_count, 0)
}

onMounted(loadSubjects)
</script>

<template>
  <div class="subjects-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
      <h1 class="title">Subject Areas</h1>
      <router-link to="/search" class="search-link">🔍 Search</router-link>
    </header>

    <main class="content">
      <!-- Loading state -->
      <div v-if="loading" class="status">
        <span class="spinner"></span>
        Loading subjects...
      </div>

      <!-- Error state -->
      <div v-else-if="error" class="status error">{{ error }}</div>

      <!-- Empty state -->
      <div v-else-if="subjects.length === 0" class="status">
        No subjects found.
      </div>

      <!-- Hierarchical subjects display -->
      <div v-else class="subjects-hierarchy">
        <section 
          v-for="(children, category) in groupedSubjects" 
          :key="category"
          class="category-section"
        >
          <h2 class="category-header">
            <span class="category-icon">{{ getIcon(category) }}</span>
            <span class="category-name">{{ category }}</span>
            <span class="category-count">{{ getCategoryEntryCount(children) }} entries</span>
          </h2>
          
          <div class="subareas-grid">
            <router-link
              v-for="subject in children"
              :key="subject.id"
              :to="`/subjects/${subject.slug}`"
              class="subarea-card"
            >
              <span class="subarea-name">{{ subject.display_name || subject.name }}</span>
              <span class="subarea-count">{{ subject.entry_count }}</span>
            </router-link>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.subjects-page {
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}

.brand {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.title {
  flex: 1;
  font-size: var(--text-lg);
  font-weight: 500;
  color: var(--text-muted);
}

.search-link {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.search-link:hover {
  color: var(--text);
  border-color: var(--text-muted);
  text-decoration: none;
}

.content {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-6);
}

.status {
  text-align: center;
  padding: var(--space-8);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

.status.error {
  color: #ef4444;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Hierarchical layout */
.subjects-hierarchy {
  display: flex;
  flex-direction: column;
  gap: var(--space-8);
}

.category-section {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.category-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  margin: 0;
  font-size: var(--text-lg);
  font-weight: 600;
}

.category-icon {
  font-size: 1.5rem;
}

.category-name {
  flex: 1;
  color: var(--text);
}

.category-count {
  font-size: var(--text-sm);
  font-weight: 400;
  color: var(--text-muted);
}

.subareas-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1px;
  background: var(--border);
}

.subarea-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-surface);
  transition: background 0.15s ease;
}

.subarea-card:hover {
  background: var(--bg);
  text-decoration: none;
}

.subarea-name {
  font-weight: 500;
  color: var(--text);
}

.subarea-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
  padding: 2px 8px;
  background: var(--bg);
  border-radius: 12px;
}
</style>
