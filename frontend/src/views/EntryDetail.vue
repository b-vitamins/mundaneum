<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api, type EntryDetail, type Collection, ApiError } from '@/api/client'
import CitationList from '@/components/CitationList.vue'

const route = useRoute()
const entry = ref<EntryDetail | null>(null)
const loading = ref(true)
const error = ref('')
const activeTab = ref('abstract')
const notes = ref('')
const notesSaved = ref(false)
const collections = ref<Collection[]>([])
const showCollectionMenu = ref(false)
const bibtex = ref('')
const showBibtex = ref(false)
const actionLoading = ref(false)

const tabs = ['abstract', 'notes', 'metadata']

const fetchEntry = async () => {
  loading.value = true
  error.value = ''
  try {
    entry.value = await api.getEntry(route.params.id as string)
    notes.value = entry.value.notes || ''
  } catch (e) {
    if (e instanceof ApiError) {
      error.value = e.detail || 'Entry not found'
    } else {
      error.value = 'Failed to load entry'
    }
  } finally {
    loading.value = false
  }
}

const fetchCollections = async () => {
  try {
    collections.value = await api.getCollections()
  } catch (e) {
    console.error('Failed to fetch collections:', e)
  }
}

// Close dropdown when clicking outside
const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.collection-dropdown')) {
    showCollectionMenu.value = false
  }
}

onMounted(() => {
  fetchEntry()
  fetchCollections()
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

const toggleRead = async () => {
  if (!entry.value || actionLoading.value) return
  actionLoading.value = true
  try {
    const newRead = !entry.value.read
    await api.toggleRead(entry.value.id, newRead)
    entry.value.read = newRead
  } catch (e) {
    console.error('Failed to toggle read:', e)
  } finally {
    actionLoading.value = false
  }
}

const saveNotes = async () => {
  if (!entry.value) return
  try {
    await api.updateNotes(entry.value.id, notes.value)
    notesSaved.value = true
    setTimeout(() => { notesSaved.value = false }, 2000)
  } catch (e) {
    console.error('Failed to save notes:', e)
  }
}

const openPdf = () => {
  if (!entry.value?.file_path) return
  window.open(`file://${entry.value.file_path}`, '_blank')
}

const copyBibtex = async () => {
  if (!entry.value) return
  try {
    if (!bibtex.value) {
      bibtex.value = await api.getBibtex(entry.value.id)
    }
    await navigator.clipboard.writeText(bibtex.value)
    showBibtex.value = true
    setTimeout(() => { showBibtex.value = false }, 2000)
  } catch (e) {
    console.error('Failed to copy BibTeX:', e)
  }
}

const addToCollection = async (collectionId: string) => {
  if (!entry.value) return
  try {
    await api.addToCollection(collectionId, entry.value.id)
    showCollectionMenu.value = false
  } catch (e) {
    console.error('Failed to add to collection:', e)
  }
}

const allFields = computed(() => {
  if (!entry.value) return []
  const fields: { key: string; value: unknown }[] = []
  
  for (const [k, v] of Object.entries(entry.value.required_fields || {})) {
    fields.push({ key: k, value: v })
  }
  for (const [k, v] of Object.entries(entry.value.optional_fields || {})) {
    fields.push({ key: k, value: v })
  }
  
  return fields
})
</script>

<template>
  <div class="entry-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
      <router-link to="/search" class="back">← Back to search</router-link>
    </header>

    <main class="content">
      <p v-if="loading" class="status">Loading...</p>
      <p v-else-if="error" class="status error">{{ error }}</p>

      <template v-else-if="entry">
        <article class="entry">
          <div class="entry-header">
            <span class="entry-type">{{ entry.entry_type }}</span>
            <h1 class="title">{{ entry.title }}</h1>
            <p class="authors">{{ entry.authors.join(', ') }}</p>
            <p class="venue">
              <span v-if="entry.venue">{{ entry.venue }}</span>
              <span v-if="entry.year">· {{ entry.year }}</span>
            </p>
          </div>

          <div class="actions">
            <button v-if="entry.file_path" class="action-btn" @click="openPdf">
              Open PDF
            </button>
            <button class="action-btn" @click="copyBibtex" :disabled="actionLoading">
              {{ showBibtex ? 'Copied!' : 'Copy BibTeX' }}
            </button>
            <button class="action-btn" @click="toggleRead" :disabled="actionLoading">
              {{ entry.read ? '✓ Read' : 'Mark as Read' }}
            </button>
            <div class="collection-dropdown">
              <button 
                class="action-btn" 
                @click.stop="showCollectionMenu = !showCollectionMenu"
              >
                Add to Collection
              </button>
              <ul v-if="showCollectionMenu" class="collection-menu">
                <li v-if="collections.length === 0" class="menu-empty">
                  No collections
                </li>
                <li
                  v-for="c in collections"
                  :key="c.id"
                  class="menu-item"
                  @click="addToCollection(c.id)"
                >
                  {{ c.name }}
                </li>
              </ul>
            </div>
          </div>

          <nav class="tabs">
            <button
              v-for="tab in ['abstract', 'notes', 'citations', 'references', 'metadata']"
              :key="tab"
              :class="['tab', { active: activeTab === tab }]"
              @click="activeTab = tab"
            >
              {{ tab }}
            </button>
          </nav>

          <section v-if="activeTab === 'abstract'" class="tab-content">
            <p v-if="entry.abstract" class="abstract">{{ entry.abstract }}</p>
            <p v-else class="empty">No abstract available</p>
          </section>

          <section v-if="activeTab === 'notes'" class="tab-content">
            <textarea
              v-model="notes"
              class="notes-input"
              placeholder="Add your notes..."
              @blur="saveNotes"
            ></textarea>
            <p v-if="notesSaved" class="notes-saved">Notes saved</p>
          </section>

          <section v-if="activeTab === 'citations'" class="tab-content">
             <CitationList :entry-id="entry.id" type="citations" />
          </section>

          <section v-if="activeTab === 'references'" class="tab-content">
             <CitationList :entry-id="entry.id" type="references" />
          </section>

          <section v-if="activeTab === 'metadata'" class="tab-content">
            <dl class="metadata-list">
              <div class="meta-row">
                <dt>Citation Key</dt>
                <dd><code>{{ entry.citation_key }}</code></dd>
              </div>
              <div class="meta-row">
                <dt>Source File</dt>
                <dd><code>{{ entry.source_file }}</code></dd>
              </div>
              <div v-for="field in allFields" :key="field.key" class="meta-row">
                <dt>{{ field.key }}</dt>
                <dd>{{ field.value }}</dd>
              </div>
            </dl>
          </section>
        </article>
      </template>
    </main>
  </div>
</template>

<style scoped>
.entry-page {
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}

.brand {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.back {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.content {
  max-width: 800px;
  margin: 0 auto;
  padding: var(--space-8);
}

.status {
  color: var(--text-muted);
  text-align: center;
}

.status.error {
  color: #ef4444;
}

.entry-header {
  margin-bottom: var(--space-6);
}

.entry-type {
  display: inline-block;
  font-size: 0.7rem;
  text-transform: uppercase;
  padding: 2px 8px;
  background: var(--border);
  border-radius: 4px;
  margin-bottom: var(--space-2);
}

.title {
  font-size: var(--text-2xl);
  font-weight: 600;
  line-height: 1.3;
  margin-bottom: var(--space-2);
}

.authors {
  color: var(--accent);
  margin-bottom: var(--space-1);
}

.venue {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-6);
}

.action-btn {
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text);
  background: var(--bg-surface);
  font-size: var(--text-sm);
}

.action-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.collection-dropdown {
  position: relative;
}

.collection-menu {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: var(--space-1);
  min-width: 180px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  list-style: none;
  z-index: 10;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.menu-item {
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
}

.menu-item:hover {
  background: var(--bg);
}

.menu-empty {
  padding: var(--space-2) var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.tabs {
  display: flex;
  gap: var(--space-1);
  border-bottom: 1px solid var(--border);
  margin-bottom: var(--space-4);
}

.tab {
  padding: var(--space-2) var(--space-4);
  color: var(--text-muted);
  font-size: var(--text-sm);
  text-transform: capitalize;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}

.tab:hover {
  color: var(--text);
}

.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-content {
  min-height: 200px;
}

.abstract {
  line-height: 1.8;
}

.empty {
  color: var(--text-muted);
}

.notes-input {
  width: 100%;
  min-height: 200px;
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-surface);
  color: var(--text);
  font-family: inherit;
  font-size: var(--text-base);
  line-height: 1.6;
  resize: vertical;
}

.notes-saved {
  color: var(--accent);
  font-size: var(--text-sm);
  margin-top: var(--space-2);
}

.metadata-list {
  display: grid;
  gap: var(--space-3);
}

.meta-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: var(--space-4);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border);
}

.meta-row dt {
  font-size: var(--text-sm);
  color: var(--text-muted);
  text-transform: capitalize;
}

.meta-row dd {
  font-size: var(--text-sm);
  word-break: break-word;
}

code {
  font-family: 'SF Mono', 'Monaco', monospace;
  font-size: 0.9em;
  padding: 2px 4px;
  background: var(--border);
  border-radius: 3px;
}
</style>
