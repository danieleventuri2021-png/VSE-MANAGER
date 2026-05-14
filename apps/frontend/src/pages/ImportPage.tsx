import { FileSpreadsheet, FolderOpen, Play, Wand2 } from "lucide-react";
import { useState } from "react";
import { analyzeJob, applyJob, importMtrFolder, uploadExcel, type Job } from "../api/client";
import { Panel } from "../components/Panel";

export function ImportPage({ jobs, onDone }: { jobs: Job[]; onDone: () => void }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [file, setFile] = useState<File | null>(null);
  const [folder, setFolder] = useState("");
  const [message, setMessage] = useState("");

  async function runExcel() {
    if (!jobId || !file) return;
    await uploadExcel(jobId, file);
    setMessage("Excel importato");
    onDone();
  }

  async function runMtr() {
    if (!jobId || !folder) return;
    await importMtrFolder(jobId, folder);
    setMessage("Cartella MTR scansionata");
    onDone();
  }

  async function runAnalyze() {
    if (!jobId) return;
    await analyzeJob(jobId);
    setMessage("Analisi completata");
    onDone();
  }

  async function runApply() {
    if (!jobId) return;
    const result = await applyJob(jobId);
    setMessage(`Applicazione completata, backup: ${result.backup_dir}`);
    onDone();
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
          <input className="text-sm" type="file" accept=".xlsx,.xls" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-4 text-sm font-medium text-white" onClick={runExcel}><FileSpreadsheet size={18} /> Importa Excel</button>
        </div>
      </Panel>
      <Panel title="Scansione MTR">
        <div className="grid gap-3">
          <input className="h-10 rounded-md border border-line px-3 text-sm" placeholder="C:\\percorso\\cartella\\mtr" value={folder} onChange={(event) => setFolder(event.target.value)} />
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-4 text-sm font-medium text-white" onClick={runMtr}><FolderOpen size={18} /> Scansiona cartella</button>
        </div>
      </Panel>
      <Panel title="Analisi e applicazione">
        <div className="flex flex-wrap gap-3">
          <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-medium" onClick={runAnalyze}><Play size={18} /> Analizza</button>
          <button className="inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-medium text-white" onClick={runApply}><Wand2 size={18} /> Applica modifiche</button>
        </div>
        {message && <p className="mt-3 text-sm text-action">{message}</p>}
      </Panel>
    </div>
  );
}
