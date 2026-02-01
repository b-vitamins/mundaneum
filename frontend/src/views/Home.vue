<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Stats } from '@/api/client'

const router = useRouter()
const query = ref('')
const stats = ref<Stats>({ entries: 0, authors: 0, collections: 0 })
const loading = ref(true)
const error = ref('')

const handleSearch = () => {
  if (query.value.trim()) {
    router.push({ name: 'search', query: { q: query.value } })
  }
}

onMounted(async () => {
  try {
    stats.value = await api.getStats()
  } catch (e) {
    error.value = 'Could not load library stats'
    console.error('Failed to fetch stats:', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="home">
    <div class="hero">
      <h1 class="logo">Folio</h1>
      <p class="tagline">Your private library</p>

      <form class="search-form" @submit.prevent="handleSearch">
        <input
          v-model="query"
          type="text"
          class="search-input"
          placeholder="Search your library..."
          autofocus
        />
        <button type="submit" class="search-button">Search</button>
      </form>

      <p v-if="loading" class="stats">Loading...</p>
      <p v-else-if="error" class="stats error">{{ error }}</p>
      <p v-else class="stats">{{ stats.entries.toLocaleString() }} entries</p>

      <nav class="quick-links">
        <router-link to="/browse" class="quick-link">Browse</router-link>
        <router-link to="/search?filter=recent" class="quick-link">Recent</router-link>
        <router-link to="/search?filter=unread" class="quick-link">Unread</router-link>
        <router-link to="/collections" class="quick-link">Collections</router-link>
        <router-link to="/admin" class="quick-link admin-link">Admin</router-link>
      </nav>
      
      <p class="hint">Press <kbd>/</kbd> to search</p>
    </div>
  </main>
</template>

<style scoped>
.home {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero {
  text-align: center;
  max-width: 600px;
  padding: var(--space-8);
}

.logo {
  font-size: var(--text-3xl);
  font-weight: 600;
  letter-spacing: -0.02em;
  margin-bottom: var(--space-2);
}

.tagline {
  color: var(--text-muted);
  margin-bottom: var(--space-8);
}

.search-form {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.search-input {
  flex: 1;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-surface);
  color: var(--text);
  font-size: var(--text-base);
}

.search-input:focus {
  outline: none;
  border-color: var(--accent);
}

.search-button {
  padding: var(--space-3) var(--space-6);
  background: var(--accent);
  color: white;
  border-radius: var(--radius);
  font-weight: 500;
}

.search-button:hover {
  opacity: 0.9;
}

.stats {
  color: var(--text-muted);
  font-size: var(--text-sm);
  margin-bottom: var(--space-6);
}

.stats.error {
  color: #ef4444;
}

.quick-links {
  display: flex;
  gap: var(--space-4);
  justify-content: center;
  margin-bottom: var(--space-6);
}

.quick-link {
  color: var(--text-muted);
  font-size: var(--text-sm);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: all 0.15s ease;
}

.quick-link:hover {
  color: var(--text);
  border-color: var(--text-muted);
  text-decoration: none;
}

.hint {
  color: var(--text-muted);
  font-size: var(--text-sm);
  opacity: 0.6;
}

kbd {
  padding: 2px 6px;
  background: var(--border);
  border-radius: 4px;
  font-family: inherit;
  font-size: 0.85em;
}
</style>
