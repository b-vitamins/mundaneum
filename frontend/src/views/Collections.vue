<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api, type Collection, ApiError } from '@/api/client'
import AppShell from '@/components/AppShell.vue'

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
  } finally {
    actionLoading.value = null
  }
}

const dismissError = () => { error.value = '' }
</script>

<template>
  <AppShell title="Collections" :show-search="true">
    <template #actions>
      <button v-if="!showNewForm" class="btn btn-primary" @click="showNewForm = true">
        + New
      </button>
    </template>

    <!-- Error banner -->
    <div v-if="error" class="error-banner card">
      <span>{{ error }}</span>
      <button class="btn btn-subtle" @click="dismissError">×</button>
    </div>

    <!-- New collection form -->
    <form v-if="showNewForm" class="new-form card" @submit.prevent="createCollection">
      <input
        v-model="newName"
        type="text"
        class="input"
        placeholder="Collection name..."
        autofocus
      />
      <button type="submit" class="btn btn-primary">Create</button>
      <button type="button" class="btn btn-ghost" @click="showNewForm = false">Cancel</button>
    </form>

    <!-- Loading -->
    <div v-if="loading" class="status">
      <span class="spinner"></span>
      Loading collections...
    </div>

    <!-- Empty state -->
    <div v-else-if="collections.length === 0" class="empty-state">
      <div class="empty-icon">📁</div>
      <h3 class="empty-title">No collections yet</h3>
      <p class="empty-text">Create a collection to organize your papers into groups.</p>
      <button v-if="!showNewForm" class="btn btn-primary" @click="showNewForm = true">
        Create your first collection
      </button>
    </div>

    <!-- Collection list -->
    <div v-else class="collection-list">
      <div v-for="c in collections" :key="c.id" class="collection-item card card-hoverable">
        <div class="collection-info">
          <span class="collection-name">{{ c.name }}</span>
          <span class="collection-count">{{ c.entry_count.toLocaleString() }} entries</span>
        </div>
        <button
          class="delete-btn btn btn-subtle"
          :disabled="actionLoading === c.id"
          @click.stop="deleteCollection(c.id, c.name)"
        >
          {{ actionLoading === c.id ? '...' : '✕' }}
        </button>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 59, 48, 0.08);
  border-color: rgba(255, 59, 48, 0.2);
  color: var(--danger);
  margin-bottom: var(--space-4);
}

.new-form {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
  align-items: center;
}
.new-form .input {
  flex: 1;
}

.status {
  text-align: center;
  padding: var(--space-12);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

.empty-state {
  text-align: center;
  padding: var(--space-16) var(--space-8);
}
.empty-icon {
  font-size: 3rem;
  margin-bottom: var(--space-4);
  opacity: 0.5;
}
.empty-title {
  font-size: var(--text-xl);
  font-weight: 600;
  margin-bottom: var(--space-2);
}
.empty-text {
  color: var(--text-muted);
  margin-bottom: var(--space-6);
}

.collection-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 640px;
}

.collection-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.collection-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.collection-name {
  font-weight: 500;
  color: var(--text);
}

.collection-count {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.delete-btn {
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
  color: var(--text-muted);
}
.collection-item:hover .delete-btn {
  opacity: 1;
}
.delete-btn:hover {
  color: var(--danger);
}
</style>
