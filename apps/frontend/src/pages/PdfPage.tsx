import { AlertCircle, Archive, CheckCircle2, Download, FileText, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { downloadAllGeneratedPdfs, downloadGeneratedPdf, generateAllPdfs, getReview, listPdfs, saveJobSettings, type Job } from "../api/client";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";

export function PdfPage({ jobs, mode = "full", onChanged }: { jobs: Job[]; mode?: "full" | "simple"; onChanged?: () => void }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [files, setFiles] = useState<any[]>([]);
  const [pdfs, setPdfs] = useState<any[]>([]);
  const [report, setReport] = useState<any>(null);
  const [status, setStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  async function refresh() {
    if (!jobId) return;
    setRefreshing(true);
    try {
      setFiles(await getReview(jobId));
      setPdfs(await listPdfs(jobId));
    } finally {
      setRefreshing(false);
    }
  }

  async function generateAll() {
    if (!jobId) return;
    setStatus("running");
    setMessage("Generazione PDF in corso...");
    setReport(null);
    try {
      const data = await generateAllPdfs(jobId);
      setReport(data);
      const errors = data.errors?.length ?? 0;
      setStatus(errors > 0 ? "error" : "success");
      setMessage(errors > 0 ? `Generati ${data.generated}/${data.total} PDF. Errori: ${errors}.` : `Generati ${data.generated}/${data.total} PDF in ${data.output_dir}.`);
      await refresh();
    } catch (error: any) {
      setStatus("error");
      setMessage(error?.response?.data?.detail || error?.message || "Generazione PDF non riuscita.");
    }
  }

  async function updateTemplate(template: string) {
    if (!jobId) return;
    await saveJobSettings(jobId, { template_pdf: template, intestazione_pdf: template });
    await onChanged?.();
  }

  const isRunning = status === "running";
  const selectedJob = jobs.find((job) => job.id === jobId);
  const modelLabel = selectedJob?.template_pdf === "consip" ? "Modello CONSIP" : "Modello generico";

  return (
    <div className="grid gap-4">
      <Panel title="Generazione PDF" action={<RefreshButton loading={refreshing} onClick={refresh} />}>
        <div className="flex flex-wrap gap-3">
          <select className="h-10 rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
            <option value={0}>Seleziona lavoro</option>
            {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
          </select>
          {jobId > 0 && <div className="inline-flex h-10 items-center rounded-md border border-line bg-slate-50 px-3 text-sm text-ink">{modelLabel}</div>}
          {mode === "simple" && jobId > 0 && (
            <select className="h-10 rounded-md border border-line px-3 text-sm" value={selectedJob?.template_pdf || "standard"} onChange={(event) => updateTemplate(event.target.value)}>
              <option value="standard">Layout generico</option>
              <option value="consip">Layout CONSIP</option>
            </select>
          )}
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md bg-action px-3 text-sm text-white disabled:cursor-not-allowed disabled:opacity-60"
            onClick={generateAll}
            disabled={!jobId || isRunning}
          >
            {isRunning ? <LoaderCircle size={16} className="animate-spin" /> : <FileText size={16} />}
            {isRunning ? "Generazione..." : "Genera tutti i PDF"}
          </button>
          <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line bg-white px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60" onClick={() => downloadAllGeneratedPdfs(jobId)} disabled={!jobId || isRunning || pdfs.length === 0}>
            <Archive size={16} /> Scarica ZIP
          </button>
        </div>
        {status !== "idle" && (
          <div className={`mt-4 rounded-md border p-3 text-sm ${status === "error" ? "border-red-200 bg-red-50 text-red-800" : status === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-sky-200 bg-sky-50 text-sky-800"}`}>
            <div className="flex items-center gap-2">
              {status === "running" && <LoaderCircle size={18} className="animate-spin" />}
              {status === "success" && <CheckCircle2 size={18} />}
              {status === "error" && <AlertCircle size={18} />}
              <span>{message}</span>
            </div>
            {status === "running" && <div className="mt-3 h-2 overflow-hidden rounded-full bg-sky-100"><div className="h-full w-1/2 animate-pulse rounded-full bg-sky-600" /></div>}
          </div>
        )}
        {report && <PdfReport report={report} />}
      </Panel>
      <Panel title="PDF generati">
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Nome</th><th>Modello</th><th>Esito</th><th>Percorso server</th><th className="text-right">Download</th></tr></thead><tbody>{pdfs.map((pdf) => <tr className="border-t border-line" key={pdf.id}><td className="py-2">{pdf.nome_pdf}</td><td>{pdf.template_pdf === "consip" ? "CONSIP" : "Generico"}</td><td>{pdf.esito}</td><td className="break-all">{pdf.percorso_pdf}</td><td className="text-right"><button className="inline-flex h-8 items-center gap-2 rounded-md border border-line px-2 text-xs disabled:cursor-not-allowed disabled:opacity-60" onClick={() => downloadGeneratedPdf(jobId, pdf.id, pdf.nome_pdf)} disabled={!jobId || pdf.esito !== "generato"}><Download size={14} /> Scarica</button></td></tr>)}</tbody></table></div>
        <p className="mt-3 text-xs text-slate-500">File MTR/CSV/DTA nel lavoro: {files.length}</p>
      </Panel>
    </div>
  );
}

function PdfReport({ report }: { report: any }) {
  const errors = report.errors || [];
  const skipped = report.skipped || [];
  const anomalies = report.anomalies || [];
  return (
    <div className="mt-4 rounded-md border border-line bg-white p-4 text-sm">
      <div className="mb-3 flex items-center gap-2 font-semibold text-ink"><FileText className="text-action" size={18} /> Risultato generazione PDF</div>
      <div className="grid gap-2 sm:grid-cols-4">
        <Metric label="Totali" value={report.total ?? 0} />
        <Metric label="Generati" value={report.generated ?? 0} tone="ok" />
        <Metric label="Errori" value={errors.length} tone={errors.length ? "error" : "ok"} />
        <Metric label="Saltati" value={skipped.length} tone={skipped.length ? "warn" : "ok"} />
      </div>
      {report.output_dir && <div className="mt-3 rounded-md border border-line bg-slate-50 p-3 text-xs text-slate-600"><span className="font-medium">Cartella output:</span> {report.output_dir}</div>}
      <IssueList title="Errori" rows={errors} tone="error" />
      <IssueList title="Saltati" rows={skipped} tone="warn" />
      <IssueList title="Anomalie" rows={anomalies} tone="warn" />
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: "ok" | "warn" | "error" }) {
  const color = tone === "error" ? "text-red-700" : tone === "warn" ? "text-amber-700" : tone === "ok" ? "text-action" : "text-ink";
  return <div className="rounded-md border border-line bg-slate-50 p-3"><div className="text-xs uppercase text-slate-500">{label}</div><div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div></div>;
}

function IssueList({ title, rows, tone }: { title: string; rows: any[]; tone: "warn" | "error" }) {
  if (!rows.length) return null;
  const colors = tone === "error" ? "border-red-200 bg-red-50 text-red-900" : "border-amber-200 bg-amber-50 text-amber-900";
  return (
    <div className={`mt-3 rounded-md border p-3 ${colors}`}>
      <div className="mb-1 font-medium">{title}</div>
      <ul className="grid gap-1 text-xs">
        {rows.map((item, index) => <li key={index}>MTR/CSV/DTA #{item.file_mtr_id || "-"}: {item.error || item.reason || item.message || "dettaglio non indicato"}</li>)}
      </ul>
    </div>
  );
}
