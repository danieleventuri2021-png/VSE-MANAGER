import { AlertCircle, CheckCircle2, ChevronLeft, FileText, Folder, FolderOpen, LoaderCircle, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { browseFolders, createFolder, deleteFolder, generateAllPdfs, getReview, listPdfs, renameFolder, type Job } from "../api/client";
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
          <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={() => setPickerOpen(true)} disabled={isRunning}><Folder size={16} /> Sfoglia</button>
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
      {pickerOpen && <FolderPicker initialPath={outputDir} onSelect={(path) => { setOutputDir(path); setPickerOpen(false); }} onClose={() => setPickerOpen(false)} />}
    </div>
  );
}

function FolderPicker({ initialPath, onSelect, onClose }: { initialPath: string; onSelect: (path: string) => void; onClose: () => void }) {
  const [path, setPath] = useState(initialPath);
  const [parent, setParent] = useState<string | null>(null);
  const [folders, setFolders] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [selectedFolder, setSelectedFolder] = useState<any>(null);
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState(false);

  async function load(nextPath?: string) {
    setError("");
    try {
      const data = await browseFolders(nextPath || undefined);
      setPath(data.path || "");
      setParent(data.parent);
      setFolders(data.folders || []);
      setSelectedFolder(null);
      setRenaming(false);
      setNewName("");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Impossibile leggere la cartella.");
    }
  }

  async function makeFolder() {
    if (!path || !newName.trim()) return;
    setError("");
    try {
      const created = await createFolder(path, newName.trim());
      await load(path);
      setPath(created.path);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Creazione cartella non riuscita.");
    }
  }

  async function applyRename() {
    if (!selectedFolder || !newName.trim()) return;
    setError("");
    try {
      const renamed = await renameFolder(selectedFolder.path, newName.trim());
      await load(renamed.path);
      setPath(renamed.path);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Rinomina cartella non riuscita.");
    }
  }

  async function removeSelected() {
    if (!selectedFolder) return;
    setError("");
    try {
      await deleteFolder(selectedFolder.path);
      await load(parentPath(selectedFolder.path));
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Eliminazione cartella non riuscita.");
    }
  }

  useEffect(() => { load(initialPath || undefined); }, []);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4">
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-md bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h3 className="text-sm font-semibold">Seleziona cartella export PDF</h3>
          <button className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="border-b border-line p-3">
          <div className="flex gap-2">
            <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm disabled:opacity-50" disabled={parent === null} onClick={() => load(parent || undefined)}><ChevronLeft size={16} /> Su</button>
            <input className="h-9 flex-1 rounded-md border border-line px-3 text-sm" value={path} onChange={(event) => setPath(event.target.value)} placeholder="Percorso cartella" />
            <button className="h-9 rounded-md border border-line px-3 text-sm" onClick={() => load(path)}>Apri</button>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <input className="h-9 min-w-56 rounded-md border border-line px-3 text-sm" value={newName} onChange={(event) => setNewName(event.target.value)} placeholder={renaming ? "Nuovo nome cartella" : "Nome nuova cartella"} />
            <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={renaming ? applyRename : makeFolder} disabled={!path || !newName.trim()}>{renaming ? <Pencil size={16} /> : <Plus size={16} />}{renaming ? "Conferma rinomina" : "Nuova cartella"}</button>
            <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm disabled:opacity-50" disabled={!selectedFolder} onClick={() => { setRenaming(true); setNewName(selectedFolder?.name || ""); }}><Pencil size={16} /> Rinomina</button>
            <button className="inline-flex h-9 items-center gap-2 rounded-md border border-red-200 px-3 text-sm text-red-700 disabled:opacity-50" disabled={!selectedFolder} onClick={removeSelected}><Trash2 size={16} /> Elimina</button>
          </div>
          {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
        </div>
        <div className="min-h-64 flex-1 overflow-auto p-2">
          {folders.map((folder) => (
            <button key={folder.path} className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-slate-100 ${selectedFolder?.path === folder.path ? "bg-blue-50 ring-1 ring-action" : ""}`} onDoubleClick={() => load(folder.path)} onClick={() => { setSelectedFolder(folder); setPath(folder.path); }}>
              <Folder size={16} className="text-slate-500" />
              <span className="truncate">{folder.name}</span>
            </button>
          ))}
          {!folders.length && <p className="p-3 text-sm text-slate-500">Nessuna sottocartella disponibile.</p>}
        </div>
        <div className="flex justify-end gap-2 border-t border-line p-3">
          <button className="h-9 rounded-md border border-line px-3 text-sm" onClick={onClose}>Annulla</button>
          <button className="h-9 rounded-md bg-action px-3 text-sm text-white" onClick={() => onSelect(path)}>Usa questa cartella</button>
        </div>
      </div>
    </div>
  );
}

function parentPath(path: string) {
  const normalized = path.replace(/[\\/]$/, "");
  const index = Math.max(normalized.lastIndexOf("\\"), normalized.lastIndexOf("/"));
  return index > 0 ? normalized.slice(0, index) : undefined;
}
