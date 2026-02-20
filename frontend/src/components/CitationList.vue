<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { api, type S2Paper } from '@/api/client'

const props = defineProps<{
  entryId: string
  type: 'citations' | 'references'
}>()

const papers = ref<S2Paper[]>([])
const loading = ref(true)
const error = ref('')

const fetchPapers = async () => {
  loading.value = true
  error.value = ''
  try {
    papers.value = props.type === 'citations'
      ? await api.getCitations(props.entryId)
      : await api.getReferences(props.entryId)
  } catch (e) {
    console.error(e)
    error.value = 'Failed to load data.'
  } finally {
    loading.value = false
  }
}

watch(() => props.type, fetchPapers)
onMounted(fetchPapers)

const expandedAbstracts = ref<Set<string>>(new Set())
const toggleAbstract = (id: string) => {
  if (expandedAbstracts.value.has(id)) expandedAbstracts.value.delete(id)
  else expandedAbstracts.value.add(id)
}
const formatAuthors = (authors: any[]) => {
  if (!authors || !authors.length) return 'Unknown Author'
  if (authors.length <= 3) return authors.map(a => a.name).join(', ')
  return authors.slice(0, 3).map(a => a.name).join(', ') + ` +${authors.length - 3} authors`
}
</script>

<template>
  <div class="citation-list">
    <div v-if="loading" class="status"><span class="spinner"></span> Loading {{ type }}...</div>
    <div v-else-if="error" class="status error">{{ error }}</div>
    <div v-else-if="papers.length === 0" class="status empty">No {{ type }} found (yet).</div>

    <div v-else class="papers">
      <article v-for="paper in papers" :key="paper.s2_id" class="paper-card card card-hoverable">
        <a class="paper-title" :href="`https://www.semanticscholar.org/paper/${paper.s2_id}`" target="_blank">
          {{ paper.title }}
        </a>

        <div class="paper-authors">{{ formatAuthors(paper.authors) }}</div>

        <div class="paper-meta">
          <span v-if="paper.venue">{{ paper.venue }}</span>
          <span v-if="paper.year">{{ paper.year }}</span>
          <span v-if="paper.citation_count" class="citation-count">{{ paper.citation_count }} citations</span>
          <span v-if="paper.is_influential" class="badge badge-warning">High Influence</span>
        </div>

        <div v-if="paper.tldr || paper.abstract" class="abstract-section">
          <div v-if="!expandedAbstracts.has(paper.s2_id) && paper.tldr" class="tldr">
            <strong>TLDR:</strong> {{ paper.tldr.text }}
            <button v-if="paper.abstract" class="btn btn-subtle expand-btn" @click="toggleAbstract(paper.s2_id)">Expand</button>
          </div>
          <div v-if="expandedAbstracts.has(paper.s2_id) || (!paper.tldr && paper.abstract)" class="abstract-full">
            {{ paper.abstract }}
            <button v-if="paper.tldr" class="btn btn-subtle expand-btn" @click="toggleAbstract(paper.s2_id)">Collapse</button>
          </div>
        </div>

        <div v-if="paper.contexts?.length" class="contexts">
          <div v-for="(ctx, i) in paper.contexts.slice(0, 2)" :key="i" class="context-item">"{{ ctx }}"</div>
          <div v-if="paper.contexts.length > 2" class="more-contexts">+ {{ paper.contexts.length - 2 }} more excerpts</div>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.citation-list { padding: var(--space-2) 0; }

.status {
  text-align: center; padding: var(--space-8); color: var(--text-muted);
  display: flex; align-items: center; justify-content: center; gap: var(--space-2);
}
.status.error { color: var(--danger); }

.papers { display: flex; flex-direction: column; gap: var(--space-3); }

.paper-card { text-decoration: none; color: inherit; }
.paper-card:hover { text-decoration: none; }

.paper-title {
  font-size: var(--text-base); font-weight: 600; color: var(--accent);
  text-decoration: none; display: block; margin-bottom: var(--space-1);
  line-height: var(--leading-tight);
}
.paper-title:hover { text-decoration: underline; }

.paper-authors { color: var(--text-muted); font-size: var(--text-sm); margin-bottom: var(--space-1); }

.paper-meta {
  display: flex; gap: var(--space-3); font-size: var(--text-sm);
  color: var(--text-muted); align-items: center; margin-bottom: var(--space-2);
}
.citation-count { font-weight: 500; }

.abstract-section {
  font-size: var(--text-sm); margin-top: var(--space-2);
  background: var(--bg); padding: var(--space-3);
  border-radius: var(--radius); line-height: var(--leading-relaxed);
}
.tldr { font-style: italic; }
.expand-btn { font-size: var(--text-xs); margin-left: var(--space-2); padding: var(--space-1) var(--space-2); }

.contexts {
  margin-top: var(--space-2); border-left: 3px solid var(--border);
  padding-left: var(--space-3);
}
.context-item {
  font-size: var(--text-sm); color: var(--text-muted);
  font-style: italic; margin-bottom: 4px;
}
.more-contexts { font-size: var(--text-xs); color: var(--text-muted); }
</style>
