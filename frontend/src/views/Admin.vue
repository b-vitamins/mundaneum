<script setup lang="ts">
import { computed, ref } from "vue";
import {
  api,
  type AdminHealth,
  type ExportData,
  type ImportResult,
} from "@/api/client";
import AppShell from "@/components/AppShell.vue";
import { useMutation } from "@/composables/useMutation";
import { usePollingResource } from "@/composables/usePollingResource";

const healthResource = usePollingResource<AdminHealth>(() =>
  api.getAdminHealth(),
);
const health = healthResource.data;
const loading = healthResource.loading;
const error = computed(() =>
  healthResource.error.value ? "Could not load health status" : "",
);
const importResult = ref<ImportResult | null>(null);
const ingestResult = ref<{
  imported: number;
  errors: number;
  total_parsed: number;
} | null>(null);

const healthStatus = computed(() => {
  if (!health.value) return "loading";
  return health.value.status === "healthy" ? "healthy" : "degraded";
});

const exportMutation = useMutation(
  async () => {
    const backupData = await api.exportBackup();
    const blob = new Blob([JSON.stringify(backupData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mundaneum-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    return backupData;
  },
  {
    successMessage: (backupData) =>
      `Exported ${backupData.entries.length} entries and ${backupData.collections.length} collections`,
    errorMessage: "Failed to export backup",
  },
);
const exportPending = exportMutation.pending;
const exportError = exportMutation.error;
const exportSuccess = exportMutation.success;

async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files?.length) return;
  try {
    const file = input.files[0];
    importResult.value = null;
    await importMutation.execute(file);
    input.value = "";
  } catch (e) {
    console.error(e);
  }
}

const importMutation = useMutation(
  async (file: File) => {
    const text = await file.text();
    const data = JSON.parse(text) as ExportData;
    return api.importBackup(data);
  },
  {
    errorMessage: (loadError) =>
      loadError instanceof SyntaxError
        ? "Invalid JSON file"
        : "Failed to import backup",
    onSuccess: async (result) => {
      importResult.value = result;
      await healthResource.fetch();
    },
  },
);
const importPending = importMutation.pending;
const importError = importMutation.error;

const ingestMutation = useMutation(async () => api.triggerIngest(), {
  errorMessage: "Failed to ingest BibTeX files",
  onSuccess: async (result) => {
    ingestResult.value = result;
    await healthResource.fetch();
  },
});
const ingestPending = ingestMutation.pending;
const ingestError = ingestMutation.error;

async function exportBackup() {
  try {
    await exportMutation.execute();
  } catch (e) {
    console.error(e);
  }
}

async function triggerIngest() {
  ingestResult.value = null;
  try {
    await ingestMutation.execute();
  } catch (e) {
    console.error(e);
  }
}
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
            <span :class="['health-value', healthStatus]">{{
              healthStatus
            }}</span>
          </div>
          <div class="health-item">
            <span class="health-label">Database</span>
            <span
              :class="[
                'health-value',
                health.database === 'ok' ? 'healthy' : 'degraded',
              ]"
              >{{ health.database }}</span
            >
          </div>
          <div class="health-item">
            <span class="health-label">Search</span>
            <span
              :class="[
                'health-value',
                health.search === 'ok' ? 'healthy' : 'degraded',
              ]"
              >{{ health.search }}</span
            >
          </div>
          <div class="health-item">
            <span class="health-label">Bibliography</span>
            <span
              :class="[
                'health-value',
                health.bibliography === 'ok' ? 'healthy' : 'degraded',
              ]"
              >{{ health.bibliography }}</span
            >
          </div>
          <div class="health-item health-item-wide">
            <span class="health-label">Repo</span>
            <code class="health-path">{{ health.bibliography_repo_url }}</code>
          </div>
          <div class="health-item health-item-wide">
            <span class="health-label">Checkout</span>
            <code class="health-path">{{
              health.bibliography_checkout_path
            }}</code>
          </div>
          <div class="health-item">
            <span class="health-label">BibTeX Files</span>
            <span class="health-value">{{ health.bib_files_count }}</span>
          </div>
        </div>
        <button
          class="btn btn-ghost"
          @click="healthResource.fetch"
          :disabled="loading"
        >
          {{ loading ? "Refreshing..." : "↻ Refresh" }}
        </button>
      </section>

      <!-- Ingest -->
      <section class="admin-card card">
        <h2 class="card-title">Bulk Ingest</h2>
        <p class="card-desc">
          Parse all BibTeX files from the configured directory and sync to
          database.
        </p>
        <button
          class="btn btn-primary"
          @click="triggerIngest"
          :disabled="ingestPending"
        >
          {{ ingestPending ? "Ingesting..." : "📥 Run Ingest" }}
        </button>
        <div v-if="ingestResult" class="result result-success">
          ✓ Imported {{ ingestResult.imported }} entries ({{
            ingestResult.total_parsed
          }}
          parsed, {{ ingestResult.errors }} errors)
        </div>
        <div v-if="ingestError" class="result result-error">
          {{ ingestError }}
        </div>
      </section>

      <!-- Backup -->
      <section class="admin-card card">
        <h2 class="card-title">Backup</h2>
        <p class="card-desc">
          Export your notes, read status, and collections as a JSON file.
        </p>
        <button
          class="btn btn-primary"
          @click="exportBackup"
          :disabled="exportPending"
        >
          {{ exportPending ? "Exporting..." : "💾 Export Backup" }}
        </button>
        <div v-if="exportSuccess" class="result result-success">
          ✓ {{ exportSuccess }}
        </div>
        <div v-if="exportError" class="result result-error">
          {{ exportError }}
        </div>
      </section>

      <!-- Restore -->
      <section class="admin-card card">
        <h2 class="card-title">Restore</h2>
        <p class="card-desc">
          Import notes, read status, and collections from a backup file.
        </p>
        <label class="btn btn-ghost file-label">
          <input
            type="file"
            accept=".json"
            @change="handleImport"
            :disabled="importPending"
            class="file-input"
          />
          {{ importPending ? "Importing..." : "📤 Choose Backup File" }}
        </label>
        <div v-if="importResult" class="result result-success">
          ✓ Updated {{ importResult.entries_updated }} entries,
          {{ importResult.collections_created }} collections created,
          {{ importResult.collections_updated }} collections updated
          <span v-if="importResult.entries_skipped"
            >({{ importResult.entries_skipped }} skipped)</span
          >
        </div>
        <div v-if="importResult?.errors?.length" class="result result-warning">
          ⚠ {{ importResult.errors.length }} warnings:
          <ul>
            <li v-for="err in importResult.errors.slice(0, 5)" :key="err">
              {{ err }}
            </li>
          </ul>
        </div>
        <div v-if="importError" class="result result-error">
          {{ importError }}
        </div>
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

.admin-card {
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
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.health-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.health-item-wide {
  grid-column: 1 / -1;
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
  color: var(--success);
}
.health-value.degraded {
  color: var(--danger);
}
.health-path {
  font-size: var(--text-xs);
  line-height: 1.5;
  white-space: normal;
  word-break: break-all;
}

.status-row {
  padding: var(--space-4);
  text-align: center;
  color: var(--text-muted);
}
.status-row.error {
  color: var(--danger);
}

.result {
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius);
  font-size: var(--text-sm);
}
.result-success {
  background: rgba(52, 199, 89, 0.08);
  color: var(--success);
  border: 1px solid rgba(52, 199, 89, 0.15);
}
.result-warning {
  background: rgba(255, 159, 10, 0.08);
  color: var(--warning);
  border: 1px solid rgba(255, 159, 10, 0.15);
}
.result-error {
  background: rgba(255, 59, 48, 0.08);
  color: var(--danger);
  border: 1px solid rgba(255, 59, 48, 0.15);
}
.result ul {
  margin-top: var(--space-2);
  padding-left: var(--space-4);
  font-size: var(--text-xs);
}

.file-input {
  display: none;
}
.file-label {
  cursor: pointer;
}
</style>
