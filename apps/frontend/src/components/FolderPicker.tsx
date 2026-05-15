import { ChevronLeft, Folder, Pencil, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { browseFolders, createFolder, deleteFolder, renameFolder } from "../api/client";

export function FolderPicker({
  initialPath,
  title = "Seleziona cartella",
  onSelect,
  onClose,
}: {
  initialPath: string;
  title?: string;
  onSelect: (path: string) => void;
  onClose: () => void;
}) {
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

  useEffect(() => {
    load(initialPath || undefined);
  }, []);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4">
      <div className="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-md bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h3 className="text-sm font-semibold">{title}</h3>
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
