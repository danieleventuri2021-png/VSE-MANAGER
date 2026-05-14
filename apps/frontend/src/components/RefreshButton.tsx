import { LoaderCircle, RefreshCw } from "lucide-react";

export function RefreshButton({ loading, onClick, label = "Aggiorna" }: { loading: boolean; onClick: () => void; label?: string }) {
  return (
    <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-70" onClick={onClick} disabled={loading}>
      {loading ? <LoaderCircle size={16} className="animate-spin" /> : <RefreshCw size={16} />}
      {loading ? "Aggiorno..." : label}
    </button>
  );
}
