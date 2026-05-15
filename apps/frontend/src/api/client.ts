import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 15000,
});

export type Job = {
  id: number;
  titolo: string;
  cliente_nome: string | null;
  stato: string;
  excel_path: string | null;
  mtr_folder: string | null;
  summary: Record<string, unknown>;
  tecnico_default?: string | null;
  firma_default_path?: string | null;
  proprieta_default?: string | null;
  periodicita_default?: string | null;
  tensione_default?: string | null;
  frequenza_default?: string | null;
  protezione_default?: string | null;
  template_pdf?: string | null;
  intestazione_pdf?: string | null;
  created_at: string;
  updated_at: string;
};

export async function getHealth() {
  const { data } = await api.get("/health");
  return data;
}

export async function getPorts() {
  const { data } = await api.get("/api/system/ports");
  return data;
}

export async function browseFolders(path?: string) {
  const { data } = await api.get("/api/system/folders", { params: path ? { path } : undefined });
  return data;
}

export async function createFolder(parent: string, name: string) {
  const { data } = await api.post("/api/system/folders", { parent, name });
  return data;
}

export async function renameFolder(path: string, name: string) {
  const { data } = await api.put("/api/system/folders", { path, name });
  return data;
}

export async function deleteFolder(path: string) {
  const { data } = await api.delete("/api/system/folders", { params: { path } });
  return data;
}

export async function getJobs(): Promise<Job[]> {
  const { data } = await api.get("/api/jobs");
  return data;
}

export async function createJob(payload: { titolo: string; cliente_nome?: string; mtr_folder?: string }) {
  const { data } = await api.post("/api/jobs", payload);
  return data as Job;
}

export async function uploadExcel(jobId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/api/jobs/${jobId}/excel`, form);
  return data as Job;
}

export async function uploadJobAsset(jobId: number, field: "firma_path" | "template_pdf" | "intestazione_pdf", file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/api/jobs/${jobId}/asset`, form, { params: { field } });
  return data as Job;
}

export async function importMtrFolder(jobId: number, folderPath: string) {
  const { data } = await api.post(`/api/jobs/${jobId}/mtr-folder`, { folder_path: folderPath });
  return data as Job;
}

export async function analyzeJob(jobId: number) {
  const { data } = await api.post(`/api/jobs/${jobId}/analyze`);
  return data as Job;
}

export async function applyJob(jobId: number) {
  const { data } = await api.post(`/api/jobs/${jobId}/apply`);
  return data;
}

export async function getReview(jobId: number) {
  const { data } = await api.get(`/api/jobs/${jobId}/review`);
  return data;
}

export async function getReviewDetail(jobId: number, fileMtrId: number) {
  const { data } = await api.get(`/api/jobs/${jobId}/review/${fileMtrId}`);
  return data;
}

export async function saveReview(jobId: number, fileMtrId: number, payload: Record<string, unknown>) {
  const { data } = await api.put(`/api/jobs/${jobId}/review/${fileMtrId}`, payload);
  return data;
}

export async function saveJobSettings(jobId: number, payload: Record<string, unknown>) {
  const { data } = await api.put(`/api/jobs/${jobId}/settings`, payload);
  return data as Job;
}

export async function applyJobDefaults(jobId: number, payload: Record<string, unknown>) {
  const { data } = await api.post(`/api/jobs/${jobId}/apply-defaults`, payload);
  return data;
}

export async function saveSource(fileMtrId: number, payload: Record<string, unknown>) {
  const { data } = await api.post(`/api/files/${fileMtrId}/save-source`, payload);
  return data;
}

export async function generateOnePdf(jobId: number, fileMtrId: number) {
  const { data } = await api.post(`/api/jobs/${jobId}/pdf/generate-one/${fileMtrId}`);
  return data;
}

export async function generateAllPdfs(jobId: number, outputDir?: string) {
  const { data } = await api.post(
    `/api/jobs/${jobId}/pdf/generate-all`,
    { output_dir: outputDir || null },
    { timeout: 300000 },
  );
  return data;
}

export async function listPdfs(jobId: number) {
  const { data } = await api.get(`/api/jobs/${jobId}/pdf`);
  return data;
}

export async function syncRegistry(jobId: number) {
  const { data } = await api.post(`/api/jobs/${jobId}/registry/sync`);
  return data;
}

export async function listAllAnomalies() {
  const { data } = await api.get("/api/anomalies", { params: { stato: "aperta" } });
  return data;
}

export async function deleteAnomaly(anomalyId: number) {
  const { data } = await api.delete(`/api/anomalies/${anomalyId}`);
  return data;
}

export async function deleteAllAnomalies() {
  const { data } = await api.delete("/api/anomalies", { params: { stato: "aperta" } });
  return data;
}

export async function listRegistryEquipment(params?: { cliente?: string; due_before?: string }) {
  const { data } = await api.get("/api/registry/equipment", { params });
  return data;
}

export async function listRegistryClients() {
  const { data } = await api.get("/api/registry/clients");
  return data as string[];
}

export async function getRegistryMeasurements(equipmentId: number) {
  const { data } = await api.get(`/api/registry/equipment/${equipmentId}/measurements`);
  return data;
}

export async function getRegistryTrend(equipmentId: number) {
  const { data } = await api.get(`/api/registry/equipment/${equipmentId}/trend`);
  return data;
}
