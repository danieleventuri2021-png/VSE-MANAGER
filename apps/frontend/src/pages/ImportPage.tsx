import { Archive, FileSpreadsheet, FolderOpen, Play, Upload, Wand2 } from "lucide-react";
import { useState } from "react";
import { analyzeJob, applyJob, importMtrFolder, uploadExcel, uploadMtrFiles, type Job } from "../api/client";
import { FolderPicker } from "../components/FolderPicker";
import { Panel } from "../components/Panel";

export function ImportPage({ jobs, onDone }: { jobs: Job[]; onDone: () => void }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [file, setFile] = useState<File | null>(null);
  const [mtrFiles, setMtrFiles] = useState<File[]>([]);
  const [folder, setFolder] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mtrPickerOpen, setMtrPickerOpen] = useState(false);

  function describeError(err: any, fallback: string) {
    return err?.response?.data?.detail || err?.message || fallback;
  }

  async function runExcel() {
    if (!jobId || !file || busy) return;
    setBusy(true);
    setError("");
    try {
      await uploadExcel(jobId, file);
      setMessage("Excel importato");
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Import Excel non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  async function runMtr() {
    if (!jobId || !folder || busy) return;
    setBusy(true);
    setError("");
    try {
      await importMtrFolder(jobId, folder);
      setMessage("Cartella MTR/CSV scansionata");
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Scansione cartella MTR/CSV non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  async function runMtrUpload() {
    if (!jobId || mtrFiles.length === 0 || busy) return;
    setBusy(true);
    setError("");
    try {
      await uploadMtrFiles(jobId, mtrFiles);
      setMessage(`Caricati ${mtrFiles.length} file MTR/CSV/ZIP`);
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Upload MTR/CSV non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  async function runAnalyze() {
    if (!jobId || busy) return;
    setBusy(true);
    setError("");
    try {
      await analyzeJob(jobId);
      setMessage("Analisi completata");
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Analisi non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  async function runApply() {
    if (!jobId || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await applyJob(jobId);
      setMessage(`Applicazione completata, backup: ${result.backup_dir}`);
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Applicazione modifiche non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Panel title="Selezione lavoro">
        <select className="h-10 w-full rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
          <option value={0}>Seleziona lavoro</option>
          {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
        </select>
      </Panel>
      <Panel title="Import Excel">
        <div className="grid gap-3">
          <input className="text-sm" type="file" accept=".xlsx,.xls" onChange={(event) => setFile(event.target.files?.[0] ?? null)} disabled={busy} />
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60" onClick={runExcel} disabled={busy || !jobId || !file}><FileSpreadsheet size={18} /> Importa Excel</button>
        </div>
      </Panel>
      <Panel title="Scansione MTR/CSV">
        <div className="grid gap-3">
          <input
            className="text-sm"
            type="file"
            multiple
            accept=".mtr,.MTR,.csv,.CSV,.zip,application/zip"
            onChange={(event) => setMtrFiles(Array.from(event.target.files ?? []))}
            disabled={busy}
          />
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60" onClick={runMtrUpload} disabled={busy || !jobId || mtrFiles.length === 0}>
            <Upload size={18} /> Carica MTR/CSV/ZIP
          </button>
          <div className="flex items-center gap-2 pt-2 text-xs font-medium uppercase text-slate-500">
            <Archive size={14} /> Cartella sul server
          </div>
          <div className="flex flex-wrap gap-2">
            <label className="flex min-w-72 flex-1 items-center gap-2 rounded-md border border-line bg-white px-3">
              <FolderOpen size={16} className="shrink-0 text-slate-500" />
              <input className="h-10 w-full border-0 bg-transparent text-sm outline-none" placeholder="C:\\percorso\\cartella\\mtr-csv" value={folder} onChange={(event) => setFolder(event.target.value)} disabled={busy} />
            </label>
            <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60" onClick={() => setMtrPickerOpen(true)} disabled={busy}><FolderOpen size={16} /> Scegli cartella</button>
          </div>
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60" onClick={runMtr} disabled={busy || !jobId || !folder}><FolderOpen size={18} /> Scansiona cartella server</button>
        </div>
      </Panel>
      <Panel title="Analisi e applicazione">
        <div className="flex flex-wrap gap-3">
          <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60" onClick={runAnalyze} disabled={busy || !jobId}><Play size={18} /> Analizza</button>
          <button className="inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60" onClick={runApply} disabled={busy || !jobId}><Wand2 size={18} /> Applica modifiche</button>
        </div>
        {message && <p className="mt-3 text-sm text-action">{message}</p>}
        {error && <p className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      </Panel>
      {mtrPickerOpen && <FolderPicker initialPath={folder} title="Seleziona cartella MTR/CSV" onSelect={(path) => { setFolder(path); setMtrPickerOpen(false); }} onClose={() => setMtrPickerOpen(false)} />}
    </div>
  );
}
