import { AlertCircle, CheckCircle2, FileText, Folder, FolderOpen, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { generateAllPdfs, getReview, listPdfs, type Job } from "../api/client";
import { FolderPicker } from "../components/FolderPicker";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";

export function PdfPage({ jobs }: { jobs: Job[] }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [files, setFiles] = useState<any[]>([]);
  const [pdfs, setPdfs] = useState<any[]>([]);
  const [report, setReport] = useState<any>(null);
  const [outputDir, setOutputDir] = useState("");
  const [status, setStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
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
      const data = await generateAllPdfs(jobId, outputDir.trim() || undefined);
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

  const isRunning = status === "running";

  return (
    <div className="grid gap-4">
      <Panel title="Generazione PDF" action={<RefreshButton loading={refreshing} onClick={refresh} />}>
        <div className="flex flex-wrap gap-3">
          <select className="h-10 rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
            <option value={0}>Seleziona lavoro</option>
            {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
          </select>
          <label className="flex min-w-72 flex-1 items-center gap-2 rounded-md border border-line bg-white px-3">
            <FolderOpen size={16} className="shrink-0 text-slate-500" />
            <input
              className="h-10 w-full border-0 bg-transparent text-sm outline-none"
              placeholder="Cartella export PDF, es. C:\\PDF\\VSE"
              value={outputDir}
              onChange={(event) => setOutputDir(event.target.value)}
              disabled={isRunning}
            />
          </label>
          <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={() => setPickerOpen(true)} disabled={isRunning}><Folder size={16} /> Scegli cartella</button>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md bg-action px-3 text-sm text-white disabled:cursor-not-allowed disabled:opacity-60"
            onClick={generateAll}
            disabled={!jobId || isRunning}
          >
            {isRunning ? <LoaderCircle size={16} className="animate-spin" /> : <FileText size={16} />}
            {isRunning ? "Generazione..." : "Genera tutti i PDF"}
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
        {report && <pre className="mt-4 overflow-auto rounded-md bg-slate-900 p-3 text-xs text-white">{JSON.stringify(report, null, 2)}</pre>}
      </Panel>
      <Panel title="PDF generati">
        <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Nome</th><th>Esito</th><th>Percorso</th></tr></thead><tbody>{pdfs.map((pdf) => <tr className="border-t border-line" key={pdf.id}><td className="py-2">{pdf.nome_pdf}</td><td>{pdf.esito}</td><td className="break-all">{pdf.percorso_pdf}</td></tr>)}</tbody></table></div>
        <p className="mt-3 text-xs text-slate-500">File MTR nel lavoro: {files.length}</p>
      </Panel>
      {pickerOpen && <FolderPicker initialPath={outputDir} title="Seleziona cartella export PDF" onSelect={(path) => { setOutputDir(path); setPickerOpen(false); }} onClose={() => setPickerOpen(false)} />}
    </div>
  );
}
