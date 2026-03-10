<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, type S2Meta } from '@/api/client'
import CitationList from '@/components/CitationList.vue'
import AppShell from '@/components/AppShell.vue'
import { useMutation } from '@/composables/useMutation'
import { usePollingResource } from '@/composables/usePollingResource'
import { useRouteResource } from '@/composables/useRouteResource'

const route = useRoute()
const activeTab = ref('abstract')
const notes = ref('')
const showCollectionMenu = ref(false)
const bibtex = ref('')
const showPdfViewer = ref(false)
const pdfUrl = ref('')

const entryId = computed(() => route.params.id as string)

const { data: entry, loading, error: entryLoadError } = useRouteResource({
  key: () => entryId.value,
  fetcher: (id) => api.getEntry(id),
})

const collectionsResource = usePollingResource(() => api.getCollections())
const collections = computed(() => collectionsResource.data.value ?? [])

const s2 = usePollingResource<S2Meta>(
  () => api.getEntryS2(entryId.value),
  { pollWhile: (d) => d.sync_status === 'syncing', interval: 5000, lazy: true }
)

const pageError = computed(() => entryLoadError.value ? 'Entry not found' : '')

const mergedAbstract = computed(() => {
  if (entry.value?.abstract) return entry.value.abstract
  if (s2.ready.value && s2.data.value?.abstract) return s2.data.value.abstract
  return null
})

const handleClickOutside = (e: MouseEvent) => {
  if (!(e.target as HTMLElement).closest('.collection-dropdown')) showCollectionMenu.value = false
}
const openPdf = () => {
  if (!entry.value?.file_path) return
  pdfUrl.value = `/api/entries/${entry.value.id}/pdf`
  showPdfViewer.value = true
}
const closePdf = () => { showPdfViewer.value = false; pdfUrl.value = '' }
const handleKeydown = (e: KeyboardEvent) => { if (e.key === 'Escape' && showPdfViewer.value) closePdf() }

watch(entryId, () => {
  activeTab.value = 'abstract'
  showCollectionMenu.value = false
  closePdf()
  s2.reset()
})

watch(entry, (currentEntry) => {
  notes.value = currentEntry?.notes || ''
  if (currentEntry) {
    void s2.fetch()
  }
}, { immediate: true })

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})
onUnmounted(() => { document.removeEventListener('click', handleClickOutside); document.removeEventListener('keydown', handleKeydown) })

const toggleReadMutation = useMutation(
  async () => {
    if (!entry.value) throw new Error('Entry not loaded')
    const nextRead = !entry.value.read
    await api.toggleRead(entry.value.id, nextRead)
    return nextRead
  },
  {
    onSuccess: (nextRead) => {
      if (entry.value) {
        entry.value.read = nextRead
      }
    },
  }
)

const saveNotesMutation = useMutation(
  async () => {
    if (!entry.value) throw new Error('Entry not loaded')
    await api.updateNotes(entry.value.id, notes.value)
    return notes.value
  },
  {
    successMessage: 'Notes saved',
    resetSuccessAfterMs: 2000,
  }
)

const bibtexMutation = useMutation(
  async () => {
    if (!entry.value) throw new Error('Entry not loaded')
    if (!bibtex.value) {
      bibtex.value = await api.getBibtex(entry.value.id)
    }
    await navigator.clipboard.writeText(bibtex.value)
    return bibtex.value
  },
  {
    successMessage: 'Copied!',
    resetSuccessAfterMs: 2000,
  }
)

const collectionMutation = useMutation(
  async (collectionId: string) => {
    if (!entry.value) throw new Error('Entry not loaded')
    await api.addToCollection(collectionId, entry.value.id)
    return collectionId
  },
  {
    onSuccess: () => {
      showCollectionMenu.value = false
    },
  }
)

const actionLoading = computed(() =>
  toggleReadMutation.pending.value ||
  saveNotesMutation.pending.value ||
  bibtexMutation.pending.value ||
  collectionMutation.pending.value
)
const notesSaved = computed(() => Boolean(saveNotesMutation.success.value))
const showBibtex = computed(() => Boolean(bibtexMutation.success.value))

const toggleRead = async () => {
  if (!entry.value || actionLoading.value) return
  try { await toggleReadMutation.execute() }
  catch (e) { console.error(e) }
}
const saveNotes = async () => {
  if (!entry.value) return
  try { await saveNotesMutation.execute() }
  catch (e) { console.error(e) }
}
const copyBibtex = async () => {
  if (!entry.value) return
  try { await bibtexMutation.execute() }
  catch (e) { console.error(e) }
}
const addToCollection = async (collectionId: string) => {
  if (!entry.value) return
  try { await collectionMutation.execute(collectionId) }
  catch (e) { console.error(e) }
}
const allFields = computed(() => {
  if (!entry.value) return []
  const fields: { key: string; value: unknown }[] = []
  for (const [k, v] of Object.entries(entry.value.required_fields || {})) fields.push({ key: k, value: v })
  for (const [k, v] of Object.entries(entry.value.optional_fields || {})) fields.push({ key: k, value: v })
  return fields
})
</script>

<template>
  <AppShell back-to="/browse" back-label="Library">
    <div v-if="loading" class="status"><span class="spinner"></span> Loading...</div>
    <div v-else-if="pageError" class="status error">{{ pageError }}</div>

    <template v-else-if="entry">
      <article class="entry-article">
        <!-- Header -->
        <div class="entry-header">
          <span class="badge badge-muted entry-type">{{ entry.entry_type }}</span>
          <h1 class="entry-title">{{ entry.title }}</h1>
          <p class="entry-authors">{{ entry.authors.join(', ') }}</p>
          <p class="entry-venue">
            <span v-if="entry.venue">{{ entry.venue }}</span>
            <span v-if="entry.year">· {{ entry.year }}</span>
          </p>
        </div>

        <!-- Actions -->
        <div class="actions">
          <button v-if="entry.file_path" class="btn btn-ghost" @click="openPdf">Open PDF</button>
          <button class="btn btn-ghost" @click="copyBibtex" :disabled="actionLoading">
            {{ showBibtex ? '✓ Copied!' : 'Copy BibTeX' }}
          </button>
          <button class="btn btn-ghost" @click="toggleRead" :disabled="actionLoading">
            {{ entry.read ? '✓ Read' : 'Mark as Read' }}
          </button>
          <router-link :to="{ name: 'graph', params: { id: entry.id } }" class="btn btn-primary">
            ◉ Citation Graph
          </router-link>
          <div class="collection-dropdown">
            <button class="btn btn-ghost" @click.stop="showCollectionMenu = !showCollectionMenu">
              Add to Collection
            </button>
            <ul v-if="showCollectionMenu" class="collection-menu card">
              <li v-if="collections.length === 0" class="menu-empty">No collections</li>
              <li v-for="c in collections" :key="c.id" class="menu-item" @click="addToCollection(c.id)">{{ c.name }}</li>
            </ul>
          </div>
        </div>

        <!-- S2 Panel -->
        <div class="s2-panel card" :class="{ 'progressive-blur': s2.syncing.value || s2.loading.value, 'progressive-ready': s2.ready.value }">
          <template v-if="s2.loading.value">
            <div class="s2-skeleton">
              <div class="progressive-skeleton" style="width: 80%; height: 1.2em; margin-bottom: 8px"></div>
              <div class="progressive-skeleton" style="width: 60%; height: 0.9em; margin-bottom: 8px"></div>
              <div class="progressive-skeleton" style="width: 40%; height: 0.9em"></div>
            </div>
          </template>
          <template v-else-if="s2.syncing.value">
            <div class="s2-syncing"><span class="spinner"></span> Fetching metadata from Semantic Scholar…</div>
          </template>
          <template v-else-if="s2.ready.value && s2.data.value?.sync_status === 'synced'">
            <p v-if="s2.data.value.tldr" class="s2-tldr"><strong>TLDR:</strong> {{ s2.data.value.tldr }}</p>
            <div class="s2-stats">
              <span v-if="s2.data.value.citation_count != null" class="s2-stat">
                <strong>{{ s2.data.value.citation_count.toLocaleString() }}</strong> citations
              </span>
              <span v-if="s2.data.value.reference_count != null" class="s2-stat">
                <strong>{{ s2.data.value.reference_count.toLocaleString() }}</strong> references
              </span>
              <span v-if="s2.data.value.influential_citation_count" class="s2-stat influential">
                <strong>{{ s2.data.value.influential_citation_count.toLocaleString() }}</strong> influential
              </span>
            </div>
            <div class="s2-tags" v-if="s2.data.value.fields_of_study.length">
              <span v-for="field in s2.data.value.fields_of_study" :key="field" class="badge badge-muted">{{ field }}</span>
              <span v-if="s2.data.value.is_open_access" class="badge badge-success">🔓 Open Access</span>
            </div>
            <div class="s2-links">
              <a v-if="s2.data.value.s2_url" :href="s2.data.value.s2_url" target="_blank">Semantic Scholar ↗</a>
              <a v-if="s2.data.value.open_access_pdf_url" :href="s2.data.value.open_access_pdf_url" target="_blank" class="oa-link">Open Access PDF ↗</a>
              <a v-if="s2.data.value.external_ids?.DOI" :href="'https://doi.org/' + s2.data.value.external_ids.DOI" target="_blank">DOI ↗</a>
            </div>
          </template>
          <template v-else-if="s2.data.value?.sync_status === 'no_match'">
            <p class="s2-no-match">Not found on Semantic Scholar</p>
          </template>
        </div>

        <!-- Tabs -->
        <nav class="tabs-nav">
          <div class="segmented">
            <button
              v-for="tab in ['abstract', 'notes', 'citations', 'references', 'metadata']"
              :key="tab"
              :class="['segmented-item', { active: activeTab === tab }]"
              @click="activeTab = tab"
            >{{ tab }}</button>
          </div>
        </nav>

        <section v-if="activeTab === 'abstract'" class="tab-content">
          <p v-if="mergedAbstract" class="abstract">{{ mergedAbstract }}</p>
          <p v-else-if="s2.syncing.value" class="empty progressive-blur">Loading abstract…</p>
          <p v-else class="empty">No abstract available</p>
        </section>

        <section v-if="activeTab === 'notes'" class="tab-content">
          <textarea v-model="notes" class="notes-input input" placeholder="Add your notes..." @blur="saveNotes"></textarea>
          <p v-if="notesSaved" class="notes-saved">✓ Notes saved</p>
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

    <!-- PDF Modal -->
    <teleport to="body">
      <div v-if="showPdfViewer" class="pdf-overlay" @click.self="closePdf">
        <div class="pdf-modal">
          <header class="pdf-header">
            <span class="pdf-title">{{ entry?.title }}</span>
            <button class="btn btn-ghost" @click="closePdf">✕ Close</button>
          </header>
          <iframe :src="pdfUrl" class="pdf-frame" title="PDF Viewer"></iframe>
        </div>
      </div>
    </teleport>
  </AppShell>
</template>

<style scoped>
.status {
  text-align: center; padding: var(--space-12); color: var(--text-muted);
  display: flex; align-items: center; justify-content: center; gap: var(--space-2);
}
.status.error { color: var(--danger); }

.entry-article { max-width: 800px; }

.entry-header { margin-bottom: var(--space-5); }
.entry-type { margin-bottom: var(--space-2); text-transform: uppercase; display: inline-block; }
.entry-title {
  font-size: var(--text-2xl); font-weight: 600; line-height: var(--leading-tight);
  margin-bottom: var(--space-2); letter-spacing: -0.01em;
}
.entry-authors { color: var(--accent); margin-bottom: var(--space-1); }
.entry-venue { color: var(--text-muted); font-size: var(--text-sm); }

.actions {
  display: flex; flex-wrap: wrap; gap: var(--space-2);
  margin-bottom: var(--space-5);
}

.collection-dropdown { position: relative; }
.collection-menu {
  position: absolute; top: 100%; left: 0; margin-top: var(--space-1);
  min-width: 180px; list-style: none; z-index: 10;
  box-shadow: var(--shadow-lg); padding: var(--space-1);
}
.menu-item {
  padding: var(--space-2) var(--space-3); cursor: pointer;
  border-radius: var(--radius-sm); font-size: var(--text-sm);
  transition: background var(--duration-fast) var(--ease-out);
}
.menu-item:hover { background: var(--accent-subtle); }
.menu-empty { padding: var(--space-2) var(--space-3); color: var(--text-muted); font-size: var(--text-sm); }

/* S2 Panel */
.s2-panel {
  margin-bottom: var(--space-5); min-height: 48px;
  transition: filter var(--duration-slow) var(--ease-out), opacity var(--duration-slow) var(--ease-out);
}
.s2-syncing {
  display: flex; align-items: center; gap: var(--space-2);
  color: var(--text-muted); font-size: var(--text-sm);
}
.s2-tldr {
  font-size: var(--text-sm); color: var(--text); line-height: var(--leading-relaxed);
  margin-bottom: var(--space-3); font-style: italic;
}
.s2-stats { display: flex; gap: var(--space-4); flex-wrap: wrap; margin-bottom: var(--space-3); }
.s2-stat { font-size: var(--text-sm); color: var(--text-muted); }
.s2-stat strong { color: var(--text); font-weight: 600; }
.s2-stat.influential strong { color: var(--warning); }
.s2-tags { display: flex; flex-wrap: wrap; gap: var(--space-1); margin-bottom: var(--space-3); }
.s2-links { display: flex; gap: var(--space-3); flex-wrap: wrap; font-size: var(--text-sm); }
.oa-link { color: var(--success); }
.s2-no-match { font-size: var(--text-sm); color: var(--text-muted); font-style: italic; }

/* Tabs */
.tabs-nav { margin-bottom: var(--space-5); }
.tab-content { min-height: 200px; }
.abstract { line-height: var(--leading-relaxed); }
.empty { color: var(--text-muted); }

.notes-input {
  min-height: 200px; resize: vertical;
  line-height: var(--leading-relaxed);
}
.notes-saved { color: var(--success); font-size: var(--text-sm); margin-top: var(--space-2); }

.metadata-list { display: grid; gap: var(--space-1); }
.meta-row {
  display: grid; grid-template-columns: 140px 1fr; gap: var(--space-4);
  padding: var(--space-2) 0; border-bottom: 1px solid var(--border-subtle);
}
.meta-row dt { font-size: var(--text-sm); color: var(--text-muted); text-transform: capitalize; }
.meta-row dd { font-size: var(--text-sm); word-break: break-word; }
code {
  font-family: 'SF Mono', 'Monaco', monospace; font-size: 0.85em;
  padding: 2px 6px; background: var(--bg); border-radius: var(--radius-sm);
}

/* PDF Modal */
.pdf-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.85);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; animation: fadeIn var(--duration-normal) var(--ease-out);
}
@keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
.pdf-modal {
  width: 95vw; height: 95vh; max-width: 1400px;
  background: var(--bg-surface); border-radius: var(--radius-lg);
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: var(--shadow-lg);
}
.pdf-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-subtle);
  background: var(--bg);
}
.pdf-title {
  font-weight: 500; font-size: var(--text-sm);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  flex: 1; margin-right: var(--space-4);
}
.pdf-frame { flex: 1; border: none; width: 100%; height: 100%; background: #333; }
</style>
