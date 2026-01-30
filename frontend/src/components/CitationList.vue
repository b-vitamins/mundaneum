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
    if (props.type === 'citations') {
      papers.value = await api.getCitations(props.entryId)
    } else {
      papers.value = await api.getReferences(props.entryId)
    }
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
  if (expandedAbstracts.value.has(id)) {
    expandedAbstracts.value.delete(id)
  } else {
    expandedAbstracts.value.add(id)
  }
}

const formatAuthors = (authors: any[]) => {
    if (!authors || !authors.length) return 'Unknown Author'
    if (authors.length <= 3) return authors.map(a => a.name).join(', ')
    return authors.slice(0, 3).map(a => a.name).join(', ') + ` +${authors.length - 3} authors`
}
</script>

<template>
  <div class="citation-list">
    <div v-if="loading" class="loading">Loading {{ type }}...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="papers.length === 0" class="empty">No {{ type }} found (yet).</div>
    
    <ul v-else class="papers">
      <li v-for="paper in papers" :key="paper.s2_id" class="paper-card">
        <div class="card-content">
          <a class="paper-title" :href="`https://www.semanticscholar.org/paper/${paper.s2_id}`" target="_blank">
            {{ paper.title }}
          </a>
          
          <div class="authors">{{ formatAuthors(paper.authors) }}</div>
          
          <div class="meta">
             <span class="venue" v-if="paper.venue">{{ paper.venue }}</span>
             <span class="year" v-if="paper.year">{{ paper.year }}</span>
             <span class="citations" v-if="paper.citation_count">{{ paper.citation_count }} Citations</span>
             <span v-if="paper.is_influential" class="badge influential">High Influence</span>
          </div>

          <!-- TLDR / Abstract -->
          <div class="abstract-section" v-if="paper.tldr || paper.abstract">
             <div v-if="!expandedAbstracts.has(paper.s2_id) && paper.tldr" class="tldr">
                <strong>TLDR:</strong> {{ paper.tldr.text }}
                <button class="expand-btn" v-if="paper.abstract" @click="toggleAbstract(paper.s2_id)">Expand</button>
             </div>
             <div v-if="expandedAbstracts.has(paper.s2_id) || (!paper.tldr && paper.abstract)" class="abstract-full">
                {{ paper.abstract }}
                <button class="expand-btn" v-if="paper.tldr" @click="toggleAbstract(paper.s2_id)">Collapse</button>
             </div>
          </div>

          <!-- Contexts -->
          <div v-if="paper.contexts?.length" class="contexts">
            <div class="context-item" v-for="(ctx, i) in paper.contexts.slice(0, 2)" :key="i">
                "{{ ctx }}"
            </div>
            <div v-if="paper.contexts.length > 2" class="more-contexts">
                 + {{ paper.contexts.length - 2 }} more excerpts
            </div>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.citation-list {
    padding: var(--space-4) 0;
}
.papers {
    list-style: none;
    padding: 0;
}
.paper-card {
    border-bottom: 1px solid var(--border);
    padding: var(--space-4) 0;
}
.paper-title {
    font-size: var(--text-lg);
    font-weight: 600;
    color: #3b82f6; /* S2 Blue-ish */
    text-decoration: none;
    display: block;
    margin-bottom: var(--space-1);
}
.paper-title:hover {
    text-decoration: underline;
}
.authors {
    color: var(--text-muted);
    margin-bottom: var(--space-1);
}
.meta {
    display: flex;
    gap: var(--space-3);
    font-size: var(--text-sm);
    color: var(--text-muted);
    align-items: center;
    margin-bottom: var(--space-2);
}
.badge.influential {
    background: #fef3c7;
    color: #d97706;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
}
.abstract-section {
    font-size: var(--text-sm);
    margin-top: var(--space-2);
    background: var(--bg-surface);
    padding: var(--space-2);
    border-radius: var(--radius);
}
.tldr {
    font-style: italic;
}
.expand-btn {
    border: none;
    background: none;
    color: var(--accent);
    cursor: pointer;
    font-size: 0.8rem;
    margin-left: var(--space-2);
}
.contexts {
    margin-top: var(--space-2);
    border-left: 3px solid var(--border);
    padding-left: var(--space-3);
}
.context-item {
    font-size: 0.85rem;
    color: var(--text-muted);
    font-style: italic;
    margin-bottom: 4px;
}
</style>
