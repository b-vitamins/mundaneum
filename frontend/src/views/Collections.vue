<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type Collection, ApiError } from '@/api/client'

const collections = ref<Collection[]>([])
const loading = ref(true)
const error = ref('')
const showNewForm = ref(false)
const newName = ref('')
const actionLoading = ref<string | null>(null)

const fetchCollections = async () => {
  loading.value = true
  error.value = ''
  try {
    collections.value = await api.getCollections()
  } catch (e) {
    error.value = 'Failed to load collections'
    console.error('Failed to fetch collections:', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchCollections)

const createCollection = async () => {
  const name = newName.value.trim()
  if (!name) return
  
  try {
    const created = await api.createCollection(name)
    collections.value.push(created)
    newName.value = ''
    showNewForm.value = false
  } catch (e) {
    if (e instanceof ApiError && e.detail) {
      error.value = e.detail
    } else {
      error.value = 'Failed to create collection'
    }
    console.error('Failed to create collection:', e)
  }
}

const deleteCollection = async (id: string, name: string) => {
  if (!confirm(`Delete "${name}"?`)) return
  
  actionLoading.value = id
  try {
    await api.deleteCollection(id)
    collections.value = collections.value.filter(c => c.id !== id)
  } catch (e) {
    error.value = 'Failed to delete collection'
    console.error('Failed to delete collection:', e)
  } finally {
    actionLoading.value = null
  }
}

const dismissError = () => {
  error.value = ''
}
</script>

<template>
  <div class="collections-page">
    <header class="header">
      <router-link to="/" class="brand">Folio</router-link>
    </header>

    <main class="content">
      <div class="page-header">
        <h1 class="page-title">Collections</h1>
        <button v-if="!showNewForm" class="new-btn" @click="showNewForm = true">
          + New
        </button>
      </div>

      <div v-if="error" class="error-banner">
        {{ error }}
        <button class="dismiss-btn" @click="dismissError">×</button>
      </div>

      <form v-if="showNewForm" class="new-form" @submit.prevent="createCollection">
        <input
          v-model="newName"
          type="text"
          class="new-input"
          placeholder="Collection name..."
          autofocus
        />
        <button type="submit" class="btn-create">Create</button>
        <button type="button" class="btn-cancel" @click="showNewForm = false">
          Cancel
        </button>
      </form>

      <p v-if="loading" class="status">Loading...</p>

      <p v-else-if="collections.length === 0" class="empty">
        No collections yet. Create one to organize your library.
      </p>

      <ul v-else class="collection-list">
        <li v-for="c in collections" :key="c.id" class="collection-item">
          <div class="collection-info">
            <span class="collection-name">{{ c.name }}</span>
            <span class="collection-count">{{ c.entry_count.toLocaleString() }} entries</span>
          </div>
          <button 
            class="delete-btn" 
            :disabled="actionLoading === c.id"
            @click="deleteCollection(c.id, c.name)"
          >
            {{ actionLoading === c.id ? 'Deleting...' : 'Delete' }}
          </button>
        </li>
      </ul>
    </main>
  </div>
</template>

<style scoped>
.collections-page {
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}

.brand {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text);
}

.content {
  max-width: 600px;
  margin: 0 auto;
  padding: var(--space-8);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-6);
}

.page-title {
  font-size: var(--text-2xl);
  font-weight: 600;
}

.new-btn {
  padding: var(--space-2) var(--space-4);
  background: var(--accent);
  color: white;
  border-radius: var(--radius);
  font-size: var(--text-sm);
  font-weight: 500;
}

.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: var(--radius);
  color: #dc2626;
  margin-bottom: var(--space-4);
}

:root[data-theme="dark"] .error-banner {
  background: #450a0a;
  border-color: #7f1d1d;
  color: #fca5a5;
}

.dismiss-btn {
  font-size: var(--text-lg);
  color: inherit;
  opacity: 0.7;
}

.dismiss-btn:hover {
  opacity: 1;
}

.new-form {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-6);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.new-input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg);
  color: var(--text);
}

.btn-create {
  padding: var(--space-2) var(--space-4);
  background: var(--accent);
  color: white;
  border-radius: var(--radius);
  font-size: var(--text-sm);
}

.btn-cancel {
  padding: var(--space-2) var(--space-4);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.status {
  color: var(--text-muted);
  text-align: center;
}

.empty {
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-12);
}

.collection-list {
  list-style: none;
}

.collection-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-4);
  border-bottom: 1px solid var(--border);
}

.collection-item:hover {
  background: var(--bg-surface);
}

.collection-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.collection-name {
  font-weight: 500;
}

.collection-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.delete-btn {
  padding: var(--space-2) var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-sm);
  opacity: 0;
  transition: opacity 0.15s;
}

.collection-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #ef4444;
}

.delete-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
