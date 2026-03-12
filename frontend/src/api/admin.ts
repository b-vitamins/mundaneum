import { client, handleError, withRetry } from "@/api/base";
import type { AdminHealth, ExportData, ImportResult } from "@/api/types";

export const adminApi = {
  async getAdminHealth(): Promise<AdminHealth> {
    try {
      const { data } = await withRetry(() => client.get("/admin/health"));
      return data;
    } catch (error) {
      return handleError(error);
    }
  },

  async exportBackup(): Promise<ExportData> {
    try {
      const { data } = await withRetry(() => client.get("/admin/export"));
      return data;
    } catch (error) {
      return handleError(error);
    }
  },

  async importBackup(backup: ExportData): Promise<ImportResult> {
    try {
      const { data } = await client.post("/admin/import", backup);
      return data;
    } catch (error) {
      return handleError(error);
    }
  },

  async triggerIngest(
    directory?: string,
  ): Promise<{ imported: number; errors: number; total_parsed: number }> {
    try {
      const { data } = await client.post("/admin/ingest/start", { directory });
      return data;
    } catch (error) {
      return handleError(error);
    }
  },

  async importBibtex(
    directory?: string,
  ): Promise<{ imported: number; errors: number; total_parsed: number }> {
    try {
      const { data } = await client.post("/ingest", { directory });
      return data;
    } catch (error) {
      return handleError(error);
    }
  },
};
