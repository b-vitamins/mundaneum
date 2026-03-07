<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Stats } from '@/api/client'
import { useDarkMode } from '@/composables/useDarkMode'

const router = useRouter()
const query = ref('')
const stats = ref<Stats>({ entries: 0, authors: 0, collections: 0 })
const loading = ref(true)
const { isDark, toggle: toggleDark } = useDarkMode()

const handleSearch = () => {
  if (query.value.trim()) {
    router.push({ name: 'search', query: { q: query.value } })
  }
}

onMounted(async () => {
  try {
    stats.value = await api.getStats()
  } catch (e) {
    console.error('Failed to fetch stats:', e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="home">
    <div class="hero">
      <button class="theme-btn" @click="toggleDark" :title="isDark ? 'Light mode' : 'Dark mode'">
        {{ isDark ? '☀️' : '🌙' }}
      </button>

      <h1 class="logo">Mundaneum</h1>
      <p class="tagline">Research intelligence for your library</p>

      <form class="search-form" @submit.prevent="handleSearch">
        <div class="search-wrapper">
          <span class="search-icon">⌕</span>
          <input
            v-model="query"
            type="text"
            class="search-input"
            placeholder="Search papers, authors, topics..."
            autofocus
          />
          <kbd class="search-kbd">/</kbd>
        </div>
      </form>

      <p v-if="!loading" class="stats">
        {{ stats.entries.toLocaleString() }} papers in your library
      </p>

      <nav class="quick-links">
        <router-link to="/browse" class="pill">Browse</router-link>
        <router-link to="/authors" class="pill">Authors</router-link>
        <router-link to="/venues" class="pill">Venues</router-link>
        <router-link to="/subjects" class="pill">Subjects</router-link>
        <router-link to="/topics" class="pill">Topics</router-link>
        <router-link to="/collections" class="pill">Collections</router-link>
      </nav>
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
  max-width: 640px;
  padding: var(--space-8);
  position: relative;
}

.theme-btn {
  position: absolute;
  top: 0;
  right: 0;
  font-size: 1.1rem;
  padding: var(--space-2);
  border-radius: var(--radius);
  transition: transform var(--duration-fast) var(--ease-out);
  cursor: pointer;
  background: none;
  border: none;
}
.theme-btn:hover {
  transform: scale(1.1);
}

.logo {
  font-size: 2.5rem;
  font-weight: 600;
  letter-spacing: -0.03em;
  margin-bottom: var(--space-1);
  color: var(--text);
}

.tagline {
  color: var(--text-muted);
  font-size: var(--text-base);
  margin-bottom: var(--space-8);
}

/* Spotlight-style search */
.search-form {
  margin-bottom: var(--space-4);
}

.search-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: var(--space-4);
  font-size: var(--text-lg);
  color: var(--text-muted);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: var(--space-3) var(--space-4) var(--space-3) 2.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  color: var(--text);
  font-size: var(--text-base);
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-fast) var(--ease-out);
}
.search-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--shadow-md), 0 0 0 3px var(--accent-subtle);
}
.search-input::placeholder {
  color: var(--text-muted);
}

.search-kbd {
  position: absolute;
  right: var(--space-3);
  padding: 2px 7px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: inherit;
  font-size: var(--text-xs);
  color: var(--text-muted);
  pointer-events: none;
}

.stats {
  color: var(--text-muted);
  font-size: var(--text-sm);
  margin-bottom: var(--space-6);
}

.quick-links {
  display: flex;
  gap: var(--space-2);
  justify-content: center;
  flex-wrap: wrap;
}

.pill {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-full);
  background: var(--accent-subtle);
  transition: all var(--duration-fast) var(--ease-out);
}
.pill:hover {
  background: var(--accent);
  color: #fff;
  text-decoration: none;
}
</style>
