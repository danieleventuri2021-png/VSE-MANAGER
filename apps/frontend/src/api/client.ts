import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/",
  timeout: 15000,
});

const TOKEN_KEY = "vse_auth_token";

api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export type CurrentUser = {
  id: number;
  username: string;
  nome: string | null;
  ruolo: string;
  attivo: boolean;
};

export type Job = {
  id: number;
  titolo: string;
  cliente_nome: string | null;
  stato: string;
  excel_path: string | null;
  mtr_folder: string | null;
  summary: Record<string, unknown>;
  workflow_mode?: "full" | "simple" | null;
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

export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export async function login(username: string, password: string) {
  const { data } = await api.post("/api/auth/login", { username, password });
  setStoredToken(data.access_token);
  return data.user as CurrentUser;
}

export async function getMe() {
  const { data } = await api.get("/api/auth/me");
  return data as CurrentUser;
}

export async function listUsers() {
  const { data } = await api.get("/api/auth/users");
  return data as CurrentUser[];
}

export async function createUser(payload: { username: string; password: string; nome?: string; ruolo?: string }) {
  const { data } = await api.post("/api/auth/users", payload);
  return data as CurrentUser;
}

export async function updateUser(userId: number, payload: { username?: string; nome?: string; ruolo?: string; attivo?: boolean; password?: string }) {
  const { data } = await api.put(`/api/auth/users/${userId}`, payload);
  return data as CurrentUser;
}

export async function deleteUser(userId: number) {
  const { data } = await api.delete(`/api/auth/users/${userId}`);
  return data;
}

export async function changePassword(payload: { old_password: string; new_password: string }) {
  const { data } = await api.post("/api/auth/change-password", payload);
  return data;
}

export async function getPorts() {
  const { data } = await api.get("/api/system/ports");
  return data;
}

export async function getDashboardStatus() {
  const { data } = await api.get("/api/dashboard/status");
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

export async function deleteJob(jobId: number, confirm: string) {
  const { data } = await api.delete(`/api/jobs/${jobId}`, { params: { confirm } });
  return data;
}

export async function createJob(payload: { titolo: string; cliente_nome?: string; mtr_folder?: string; workflow_mode?: "full" | "simple" }) {
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

export async function uploadMtrFiles(jobId: number, files: File[]) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  const { data } = await api.post(`/api/jobs/${jobId}/mtr-upload`, form, { timeout: 300000 });
  return data as Job;
}

export async function analyzeJob(jobId: number) {
  const { data } = await api.post(`/api/jobs/${jobId}/analyze`, undefined, { timeout: 300000 });
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

export async function downloadGeneratedPdf(jobId: number, pdfId: number, filename: string) {
  const { data } = await api.get(`/api/jobs/${jobId}/pdf/${pdfId}/download`, { responseType: "blob", timeout: 300000 });
  downloadBlob(data, filename || `pdf_${pdfId}.pdf`);
}

export async function downloadAllGeneratedPdfs(jobId: number) {
  const { data } = await api.get(`/api/jobs/${jobId}/pdf/download-all`, { responseType: "blob", timeout: 300000 });
  downloadBlob(data, `pdf_lavoro_${jobId}.zip`);
}

function downloadBlob(data: Blob, filename: string) {
  const url = window.URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
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

export async function deleteRegistryEquipment(ids: number[], confirm: string) {
  const { data } = await api.delete("/api/registry/equipment", { data: { ids, confirm } });
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
