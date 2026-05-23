import { Archive, CheckCircle2, FileSpreadsheet, FolderOpen, GitCompare, Play, ShieldAlert, Upload, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { analyzeJob, applyJob, createJob, importMtrFolder, uploadExcel, uploadMtrFiles, type Job } from "../api/client";
import { FolderPicker } from "../components/FolderPicker";
import { Panel } from "../components/Panel";

export function ImportPage({ jobs, mode = "full", onDone }: { jobs: Job[]; mode?: "full" | "simple"; onDone: () => void }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [file, setFile] = useState<File | null>(null);
  const [mtrFiles, setMtrFiles] = useState<File[]>([]);
  const [folder, setFolder] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [mtrPickerOpen, setMtrPickerOpen] = useState(false);
  const [operationSummary, setOperationSummary] = useState<Record<string, any> | null>(null);

  function describeError(err: any, fallback: string) {
    return err?.response?.data?.detail || err?.message || fallback;
  }

  async function effectiveJobId() {
    if (jobId) return jobId;
    if (mode !== "simple") return 0;
    const job = await createJob({ titolo: "Generazione PDF", workflow_mode: "simple" });
    setJobId(job.id);
    onDone();
    return job.id;
  }

  useEffect(() => {
    if ((!jobId || !jobs.some((job) => job.id === jobId)) && jobs[0]) {
      setJobId(jobs[0].id);
    }
  }, [jobs, jobId]);

  async function runExcel() {
    if (!jobId || !file || busy) return;
    setBusy(true);
    setError("");
    try {
      await uploadExcel(jobId, file);
      setMessage("Excel importato");
      setOperationSummary(null);
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Import Excel non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  async function runMtr() {
    if ((!jobId && mode !== "simple") || !folder || busy) return;
    setBusy(true);
    setError("");
    try {
      const currentJobId = await effectiveJobId();
      if (!currentJobId) return;
      const job = await importMtrFolder(currentJobId, folder);
      const skipped = Number(job.summary.mtr_duplicates_skipped || 0);
      setMessage(skipped ? `Cartella scansionata: ${skipped} misura gia presente non inserita` : "Cartella MTR/CSV/DTA scansionata");
      setOperationSummary({ type: "mtr", ...job.summary });
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Scansione cartella MTR/CSV/DTA non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  async function runMtrUpload() {
    if ((!jobId && mode !== "simple") || mtrFiles.length === 0 || busy) return;
    setBusy(true);
    setError("");
    try {
      const currentJobId = await effectiveJobId();
      if (!currentJobId) return;
      const job = await uploadMtrFiles(currentJobId, mtrFiles);
      const skipped = Number(job.summary.mtr_duplicates_skipped || 0);
      setMessage(skipped ? `Upload completato: ${skipped} misura gia presente non inserita` : `Caricati ${mtrFiles.length} file MTR/CSV/DTA/ZIP`);
      setOperationSummary({ type: "mtr", ...job.summary });
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Upload MTR/CSV/DTA non riuscito."));
    } finally {
      setBusy(false);
    }
  }

  async function runAnalyze() {
    if (!jobId || busy) return;
    setBusy(true);
    setError("");
    try {
      const job = await analyzeJob(jobId);
      setMessage("Analisi completata");
      setOperationSummary({ type: "analyze", ...job.summary });
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
      setOperationSummary({ type: "apply", renamed: result.renamed?.length ?? 0, backup_dir: result.backup_dir });
      onDone();
    } catch (err: any) {
      setError(describeError(err, "Applicazione modifiche non riuscita."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {mode === "full" && (
        <Panel title="Selezione lavoro">
          <select className="h-10 w-full rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
            <option value={0}>Seleziona lavoro</option>
            {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
          </select>
        </Panel>
      )}
      {mode === "simple" && <Panel title="Lavoro automatico"><p className="text-sm text-slate-600">Al primo caricamento viene usato o creato automaticamente il lavoro fittizio <strong>Generazione PDF</strong>.</p></Panel>}
      {mode === "full" && (
        <Panel title="Import Excel">
          <div className="grid gap-3">
            <input className="text-sm" type="file" accept=".xlsx,.xls" onChange={(event) => setFile(event.target.files?.[0] ?? null)} disabled={busy} />
            <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60" onClick={runExcel} disabled={busy || !jobId || !file}><FileSpreadsheet size={18} /> Importa Excel</button>
          </div>
        </Panel>
      )}
      <Panel title="Scansione MTR/CSV/DTA">
        <div className="grid gap-3">
          <input
            className="text-sm"
            type="file"
            multiple
            accept=".mtr,.MTR,.csv,.CSV,.dta,.DTA,.zip,application/zip"
            onChange={(event) => setMtrFiles(Array.from(event.target.files ?? []))}
            disabled={busy}
          />
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60" onClick={runMtrUpload} disabled={busy || (mode === "full" && !jobId) || mtrFiles.length === 0}>
            <Upload size={18} /> Carica MTR/CSV/DTA/ZIP
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
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60" onClick={runMtr} disabled={busy || (mode === "full" && !jobId) || !folder}><FolderOpen size={18} /> Scansiona cartella server</button>
        </div>
      </Panel>
      {mode === "full" ? (
        <Panel title="Analisi e applicazione">
          <div className="mb-3 grid gap-2 rounded-md border border-line bg-slate-50 p-3 text-sm text-slate-700">
            <p><strong>Analizza</strong> confronta le righe Excel con i file MTR/CSV/DTA, crea gli abbinamenti e segnala mancanti, orfani e differenze da controllare.</p>
            <p><strong>Applica modifiche</strong> scrive nei sorgenti MTR/CSV/DTA i dati confermati e rinomina i file, creando prima un backup.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60" onClick={runAnalyze} disabled={busy || !jobId}><Play size={18} /> Analizza</button>
            <button className="inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60" onClick={runApply} disabled={busy || !jobId}><Wand2 size={18} /> Applica modifiche</button>
          </div>
          {operationSummary && <OperationSummary summary={operationSummary} />}
          {message && <p className="mt-3 text-sm text-action">{message}</p>}
          {error && <p className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        </Panel>
      ) : (
        <Panel title="Importazione semplificata">
          {operationSummary && <OperationSummary summary={operationSummary} />}
          {message && <p className="text-sm text-action">{message}</p>}
          {error && <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        </Panel>
      )}
      {mtrPickerOpen && <FolderPicker initialPath={folder} title="Seleziona cartella MTR/CSV/DTA" onSelect={(path) => { setFolder(path); setMtrPickerOpen(false); }} onClose={() => setMtrPickerOpen(false)} />}
    </div>
  );
}

function OperationSummary({ summary }: { summary: Record<string, any> }) {
  if (summary.type === "mtr") {
    const details = Array.isArray(summary.mtr_duplicate_details) ? summary.mtr_duplicate_details : [];
    return (
      <div className="mt-3 grid gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
        <div className="flex items-center gap-2 font-medium"><ShieldAlert size={16} /> Import MTR/CSV/DTA</div>
        <div className="grid gap-2 sm:grid-cols-3">
          <Metric label="File letti" value={summary.mtr_files_scanned ?? 0} />
          <Metric label="File inseriti" value={summary.mtr_files ?? 0} />
          <Metric label="Duplicati saltati" value={summary.mtr_duplicates_skipped ?? 0} />
        </div>
        {details.length > 0 && (
          <div className="max-h-40 overflow-auto rounded-md border border-amber-200 bg-white/70">
            <table className="w-full text-left text-xs">
              <thead className="text-amber-800"><tr><th className="p-2">File</th><th>Identificativo</th><th>Data</th><th>Motivo</th></tr></thead>
              <tbody>
                {details.map((item: any, index: number) => (
                  <tr key={`${item.nome_file}-${index}`} className="border-t border-amber-100">
                    <td className="p-2">{item.nome_file || "-"}</td>
                    <td>{item.identificativo || "-"}</td>
                    <td>{item.data_verifica || "-"}</td>
                    <td>{item.reason || "gia presente"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }
  if (summary.type === "apply") {
    return (
      <div className="mt-3 grid gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
        <div className="flex items-center gap-2 font-medium"><CheckCircle2 size={16} /> Modifiche applicate</div>
        <div className="grid gap-2 sm:grid-cols-2">
          <Metric label="File rinominati" value={summary.renamed ?? 0} />
          <Metric label="Backup" value={summary.backup_dir || "-"} />
        </div>
      </div>
    );
  }
  const items = [
    { label: "Certi", value: summary.certo ?? 0, icon: CheckCircle2, tone: "text-emerald-700" },
    { label: "Da controllare", value: summary.da_controllare ?? 0, icon: ShieldAlert, tone: "text-amber-700" },
    { label: "Mancanti", value: summary.mancante ?? 0, icon: ShieldAlert, tone: "text-rose-700" },
    { label: "MTR/CSV/DTA orfani", value: summary.mtr_orfano ?? 0, icon: Archive, tone: "text-sky-700" },
    { label: "Differenze", value: summary.differenze ?? 0, icon: GitCompare, tone: "text-slate-700" },
  ];
  const total = items.reduce((sum, item) => sum + Number(item.value || 0), 0) || 1;
  return (
    <div className="mt-3 rounded-md border border-line bg-white p-3">
      <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-800"><GitCompare size={16} /> Resoconto analisi</div>
      <div className="grid gap-2 sm:grid-cols-5">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="rounded-md border border-line p-2">
              <div className={`flex items-center gap-1 text-xs ${item.tone}`}><Icon size={14} /> {item.label}</div>
              <div className="mt-1 text-xl font-semibold text-ink">{item.value}</div>
              <div className="mt-2 h-1.5 rounded bg-slate-100"><div className="h-1.5 rounded bg-action" style={{ width: `${Math.min(100, (Number(item.value || 0) / total) * 100)}%` }} /></div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded-md border border-emerald-200 bg-white/70 p-2"><div className="text-xs uppercase text-emerald-700">{label}</div><div className="mt-1 break-all font-medium">{value}</div></div>;
}
