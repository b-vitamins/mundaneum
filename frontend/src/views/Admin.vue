<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api, type AdminHealth, type ExportData, type ImportResult } from '@/api/client'

// State
const health = ref<AdminHealth | null>(null)
const loading = ref(true)
const error = ref('')

// Backup state
const backupData = ref<ExportData | null>(null)
const backupLoading = ref(false)
const backupError = ref('')
const backupSuccess = ref('')

// Import state
const importResult = ref<ImportResult | null>(null)
const importLoading = ref(false)
const importError = ref('')

// Ingest state
const ingestLoading = ref(false)
const ingestResult = ref<{ imported: number; errors: number; total_parsed: number } | null>(null)
const ingestError = ref('')

// Computed
const healthStatus = computed(() => {
  if (!health.value) return 'loading'
  if (health.value.status === 'healthy') return 'healthy'
  return 'degraded'
})

// Actions
async function loadHealth() {
  try {
    health.value = await api.getAdminHealth()
  } catch (e) {
    error.value = 'Could not load health status'
    console.error('Failed to fetch health:', e)
  } finally {
    loading.value = false
  }
}

async function exportBackup() {
  backupLoading.value = true
  backupError.value = ''
  backupSuccess.value = ''
  
  try {
    backupData.value = await api.exportBackup()
    
    // Create downloadable file
    const blob = new Blob([JSON.stringify(backupData.value, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `folio-backup-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    
    backupSuccess.value = `Exported ${backupData.value.entries.length} entries and ${backupData.value.collections.length} collections`
  } catch (e) {
    backupError.value = 'Failed to export backup'
    console.error('Export failed:', e)
  } finally {
    backupLoading.value = false
  }
}

async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  
  importLoading.value = true
  importError.value = ''
  importResult.value = null
  
  try {
    const file = input.files[0]
    const text = await file.text()
    const data = JSON.parse(text) as ExportData
    
    importResult.value = await api.importBackup(data)
    
    // Clear file input
    input.value = ''
    
    // Refresh health
    await loadHealth()
  } catch (e) {
    importError.value = e instanceof SyntaxError ? 'Invalid JSON file' : 'Failed to import backup'
    console.error('Import failed:', e)
  } finally {
    importLoading.value = false
  }
}

async function triggerIngest() {
  ingestLoading.value = true
  ingestError.value = ''
  ingestResult.value = null
  
  try {
    ingestResult.value = await api.triggerIngest()
    
    // Refresh health
    await loadHealth()
  } catch (e) {
    ingestError.value = 'Failed to ingest BibTeX files'
    console.error('Ingest failed:', e)
  } finally {
    ingestLoading.value = false
  }
}

onMounted(loadHealth)
</script>

<template>
  <main class="admin">
    <header class="header">
      <router-link to="/" class="back">← Back</router-link>
      <h1>Admin Panel</h1>
    </header>

    <div class="content">
      <!-- Health Status Section -->
      <section class="card">
        <h2 class="card-title">System Health</h2>
        
        <div v-if="loading" class="status-row">
          <span>Loading...</span>
        </div>
        
        <div v-else-if="error" class="status-row error">
          {{ error }}
        </div>
        
        <div v-else-if="health" class="health-grid">
          <div class="health-item">
            <span class="health-label">Status</span>
            <span :class="['health-value', healthStatus]">{{ healthStatus }}</span>
          </div>
          <div class="health-item">
            <span class="health-label">Database</span>
            <span :class="['health-value', health.database === 'ok' ? 'healthy' : 'degraded']">
              {{ health.database }}
            </span>
          </div>
          <div class="health-item">
            <span class="health-label">Search</span>
            <span :class="['health-value', health.search === 'ok' ? 'healthy' : 'degraded']">
              {{ health.search }}
            </span>
          </div>
          <div class="health-item">
            <span class="health-label">BibTeX Directory</span>
            <span :class="['health-value', health.bib_directory === 'ok' ? 'healthy' : 'degraded']">
              {{ health.bib_directory }}
            </span>
          </div>
          <div class="health-item">
            <span class="health-label">BibTeX Files</span>
            <span class="health-value">{{ health.bib_files_count }}</span>
          </div>
        </div>
        
        <button class="refresh-btn" @click="loadHealth" :disabled="loading">
          {{ loading ? 'Refreshing...' : '↻ Refresh' }}
        </button>
      </section>

      <!-- Ingest Section -->
      <section class="card">
        <h2 class="card-title">Bulk Ingest</h2>
        <p class="card-desc">Parse all BibTeX files from the configured directory and sync to database.</p>
        
        <button 
          class="action-btn" 
          @click="triggerIngest" 
          :disabled="ingestLoading"
        >
          {{ ingestLoading ? 'Ingesting...' : '📥 Run Ingest' }}
        </button>
        
        <div v-if="ingestResult" class="result success">
          ✓ Imported {{ ingestResult.imported }} entries 
          ({{ ingestResult.total_parsed }} parsed, {{ ingestResult.errors }} errors)
        </div>
        <div v-if="ingestError" class="result error">{{ ingestError }}</div>
      </section>

      <!-- Backup Section -->
      <section class="card">
        <h2 class="card-title">Backup</h2>
        <p class="card-desc">Export your notes, read status, and collections as a JSON file.</p>
        
        <button 
          class="action-btn" 
          @click="exportBackup" 
          :disabled="backupLoading"
        >
          {{ backupLoading ? 'Exporting...' : '💾 Export Backup' }}
        </button>
        
        <div v-if="backupSuccess" class="result success">✓ {{ backupSuccess }}</div>
        <div v-if="backupError" class="result error">{{ backupError }}</div>
      </section>

      <!-- Restore Section -->
      <section class="card">
        <h2 class="card-title">Restore</h2>
        <p class="card-desc">Import notes, read status, and collections from a backup file.</p>
        
        <label class="file-input-label">
          <input 
            type="file" 
            accept=".json" 
            @change="handleImport" 
            :disabled="importLoading"
            class="file-input"
          />
          {{ importLoading ? 'Importing...' : '📤 Choose Backup File' }}
        </label>
        
        <div v-if="importResult" class="result success">
          ✓ Updated {{ importResult.entries_updated }} entries, 
          {{ importResult.collections_created }} collections created,
          {{ importResult.collections_updated }} collections updated
          <span v-if="importResult.entries_skipped"> ({{ importResult.entries_skipped }} skipped)</span>
        </div>
        <div v-if="importResult?.errors?.length" class="result warning">
          ⚠ {{ importResult.errors.length }} warnings:
          <ul>
            <li v-for="err in importResult.errors.slice(0, 5)" :key="err">{{ err }}</li>
          </ul>
        </div>
        <div v-if="importError" class="result error">{{ importError }}</div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.admin {
  min-height: 100vh;
  padding: var(--space-6);
  max-width: 800px;
  margin: 0 auto;
}

.header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-8);
}

.back {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.back:hover {
  color: var(--text);
  text-decoration: none;
}

h1 {
  font-size: var(--text-2xl);
  font-weight: 600;
}

.content {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: 600;
  margin-bottom: var(--space-2);
}

.card-desc {
  color: var(--text-muted);
  font-size: var(--text-sm);
  margin-bottom: var(--space-4);
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}

.health-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.health-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.health-value {
  font-weight: 500;
}

.health-value.healthy {
  color: #22c55e;
}

.health-value.degraded {
  color: #ef4444;
}

.refresh-btn {
  padding: var(--space-2) var(--space-4);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
}

.refresh-btn:hover:not(:disabled) {
  color: var(--text);
  border-color: var(--text-muted);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn {
  padding: var(--space-3) var(--space-6);
  background: var(--accent);
  color: white;
  border-radius: var(--radius);
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.action-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.file-input {
  display: none;
}

.file-input-label {
  display: inline-block;
  padding: var(--space-3) var(--space-6);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.file-input-label:hover {
  border-color: var(--text-muted);
}

.result {
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius);
  font-size: var(--text-sm);
}

.result.success {
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.result.warning {
  background: rgba(234, 179, 8, 0.1);
  color: #eab308;
  border: 1px solid rgba(234, 179, 8, 0.2);
}

.result.error {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.result ul {
  margin-top: var(--space-2);
  padding-left: var(--space-4);
  font-size: var(--text-xs);
}

.status-row {
  padding: var(--space-4);
  text-align: center;
  color: var(--text-muted);
}

.status-row.error {
  color: #ef4444;
}
</style>
