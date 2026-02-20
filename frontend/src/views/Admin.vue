<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { api, type AdminHealth, type ExportData, type ImportResult } from '@/api/client'
import AppShell from '@/components/AppShell.vue'

const health = ref<AdminHealth | null>(null)
const loading = ref(true)
const error = ref('')
const backupData = ref<ExportData | null>(null)
const backupLoading = ref(false)
const backupError = ref('')
const backupSuccess = ref('')
const importResult = ref<ImportResult | null>(null)
const importLoading = ref(false)
const importError = ref('')
const ingestLoading = ref(false)
const ingestResult = ref<{ imported: number; errors: number; total_parsed: number } | null>(null)
const ingestError = ref('')

const healthStatus = computed(() => {
  if (!health.value) return 'loading'
  return health.value.status === 'healthy' ? 'healthy' : 'degraded'
})

async function loadHealth() {
  try { health.value = await api.getAdminHealth() }
  catch (e) { error.value = 'Could not load health status'; console.error(e) }
  finally { loading.value = false }
}

async function exportBackup() {
  backupLoading.value = true; backupError.value = ''; backupSuccess.value = ''
  try {
    backupData.value = await api.exportBackup()
    const blob = new Blob([JSON.stringify(backupData.value, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `folio-backup-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    backupSuccess.value = `Exported ${backupData.value.entries.length} entries and ${backupData.value.collections.length} collections`
  } catch (e) { backupError.value = 'Failed to export backup'; console.error(e) }
  finally { backupLoading.value = false }
}

async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement
  if (!input.files?.length) return
  importLoading.value = true; importError.value = ''; importResult.value = null
  try {
    const file = input.files[0]
    const text = await file.text()
    const data = JSON.parse(text) as ExportData
    importResult.value = await api.importBackup(data)
    input.value = ''
    await loadHealth()
  } catch (e) {
    importError.value = e instanceof SyntaxError ? 'Invalid JSON file' : 'Failed to import backup'
  } finally { importLoading.value = false }
}

async function triggerIngest() {
  ingestLoading.value = true; ingestError.value = ''; ingestResult.value = null
  try { ingestResult.value = await api.triggerIngest(); await loadHealth() }
  catch (e) { ingestError.value = 'Failed to ingest BibTeX files'; console.error(e) }
  finally { ingestLoading.value = false }
}

onMounted(loadHealth)
</script>

<template>
  <AppShell title="Admin">
    <div class="admin-content">
      <!-- Health -->
      <section class="admin-card card">
        <h2 class="card-title">System Health</h2>
        <div v-if="loading" class="status-row">Loading...</div>
        <div v-else-if="error" class="status-row error">{{ error }}</div>
        <div v-else-if="health" class="health-grid">
          <div class="health-item">
            <span class="health-label">Status</span>
            <span :class="['health-value', healthStatus]">{{ healthStatus }}</span>
          </div>
          <div class="health-item">
            <span class="health-label">Database</span>
            <span :class="['health-value', health.database === 'ok' ? 'healthy' : 'degraded']">{{ health.database }}</span>
          </div>
          <div class="health-item">
            <span class="health-label">Search</span>
            <span :class="['health-value', health.search === 'ok' ? 'healthy' : 'degraded']">{{ health.search }}</span>
          </div>
          <div class="health-item">
            <span class="health-label">BibTeX Directory</span>
            <span :class="['health-value', health.bib_directory === 'ok' ? 'healthy' : 'degraded']">{{ health.bib_directory }}</span>
          </div>
          <div class="health-item">
            <span class="health-label">BibTeX Files</span>
            <span class="health-value">{{ health.bib_files_count }}</span>
          </div>
        </div>
        <button class="btn btn-ghost" @click="loadHealth" :disabled="loading">
          {{ loading ? 'Refreshing...' : '↻ Refresh' }}
        </button>
      </section>

      <!-- Ingest -->
      <section class="admin-card card">
        <h2 class="card-title">Bulk Ingest</h2>
        <p class="card-desc">Parse all BibTeX files from the configured directory and sync to database.</p>
        <button class="btn btn-primary" @click="triggerIngest" :disabled="ingestLoading">
          {{ ingestLoading ? 'Ingesting...' : '📥 Run Ingest' }}
        </button>
        <div v-if="ingestResult" class="result result-success">
          ✓ Imported {{ ingestResult.imported }} entries ({{ ingestResult.total_parsed }} parsed, {{ ingestResult.errors }} errors)
        </div>
        <div v-if="ingestError" class="result result-error">{{ ingestError }}</div>
      </section>

      <!-- Backup -->
      <section class="admin-card card">
        <h2 class="card-title">Backup</h2>
        <p class="card-desc">Export your notes, read status, and collections as a JSON file.</p>
        <button class="btn btn-primary" @click="exportBackup" :disabled="backupLoading">
          {{ backupLoading ? 'Exporting...' : '💾 Export Backup' }}
        </button>
        <div v-if="backupSuccess" class="result result-success">✓ {{ backupSuccess }}</div>
        <div v-if="backupError" class="result result-error">{{ backupError }}</div>
      </section>

      <!-- Restore -->
      <section class="admin-card card">
        <h2 class="card-title">Restore</h2>
        <p class="card-desc">Import notes, read status, and collections from a backup file.</p>
        <label class="btn btn-ghost file-label">
          <input type="file" accept=".json" @change="handleImport" :disabled="importLoading" class="file-input" />
          {{ importLoading ? 'Importing...' : '📤 Choose Backup File' }}
        </label>
        <div v-if="importResult" class="result result-success">
          ✓ Updated {{ importResult.entries_updated }} entries,
          {{ importResult.collections_created }} collections created,
          {{ importResult.collections_updated }} collections updated
          <span v-if="importResult.entries_skipped">({{ importResult.entries_skipped }} skipped)</span>
        </div>
        <div v-if="importResult?.errors?.length" class="result result-warning">
          ⚠ {{ importResult.errors.length }} warnings:
          <ul><li v-for="err in importResult.errors.slice(0, 5)" :key="err">{{ err }}</li></ul>
        </div>
        <div v-if="importError" class="result result-error">{{ importError }}</div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.admin-content {
  max-width: 700px;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.admin-card { padding: var(--space-6); }
.card-title { font-size: var(--text-lg); font-weight: 600; margin-bottom: var(--space-2); }
.card-desc { color: var(--text-muted); font-size: var(--text-sm); margin-bottom: var(--space-4); }

.health-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-4); margin-bottom: var(--space-4);
}
.health-item { display: flex; flex-direction: column; gap: var(--space-1); }
.health-label { font-size: var(--text-xs); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.health-value { font-weight: 500; }
.health-value.healthy { color: var(--success); }
.health-value.degraded { color: var(--danger); }

.status-row { padding: var(--space-4); text-align: center; color: var(--text-muted); }
.status-row.error { color: var(--danger); }

.result {
  margin-top: var(--space-4); padding: var(--space-3) var(--space-4);
  border-radius: var(--radius); font-size: var(--text-sm);
}
.result-success { background: rgba(52, 199, 89, 0.08); color: var(--success); border: 1px solid rgba(52, 199, 89, 0.15); }
.result-warning { background: rgba(255, 159, 10, 0.08); color: var(--warning); border: 1px solid rgba(255, 159, 10, 0.15); }
.result-error { background: rgba(255, 59, 48, 0.08); color: var(--danger); border: 1px solid rgba(255, 59, 48, 0.15); }
.result ul { margin-top: var(--space-2); padding-left: var(--space-4); font-size: var(--text-xs); }

.file-input { display: none; }
.file-label { cursor: pointer; }
</style>
