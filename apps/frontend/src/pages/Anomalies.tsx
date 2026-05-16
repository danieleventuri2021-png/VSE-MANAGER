import { CheckCheck, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { deleteAllAnomalies, deleteAnomaly, listAllAnomalies } from "../api/client";
import { Badge } from "../components/Badge";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";
import { formatItalianDateTime } from "../lib/date";

export function Anomalies({ onChanged }: { onChanged: () => void }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setRows(await listAllAnomalies());
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Caricamento anomalie non riuscito.");
    } finally {
      setLoading(false);
    }
  }

  async function removeOne(id: number) {
    setWorking(true);
    setError("");
    try {
      await deleteAnomaly(id);
      await load();
      onChanged();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Cancellazione anomalia non riuscita.");
    } finally {
      setWorking(false);
    }
  }

  async function removeAll() {
    if (!rows.length) return;
    const first = window.confirm(`Cancellare tutte le ${rows.length} anomalie visualizzate?`);
    if (!first) return;
    setWorking(true);
    setError("");
    try {
      await deleteAllAnomalies();
      await load();
      onChanged();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Cancellazione anomalie non riuscita.");
    } finally {
      setWorking(false);
    }
  }

  const grouped = useMemo(() => {
    const groups: Record<string, any[]> = {};
    for (const row of rows) {
      const key = `${row.lavoro_id} - ${row.lavoro_titolo || "Lavoro senza titolo"}`;
      groups[key] = [...(groups[key] || []), row];
    }
    return Object.entries(groups);
  }, [rows]);

  useEffect(() => { load(); }, []);

  return (
    <Panel title={`Anomalie aperte (${rows.length})`} action={<RefreshButton loading={loading} onClick={load} />}>
      <div className="mb-4 flex justify-end">
        <button className="inline-flex h-10 items-center gap-2 rounded-md border border-red-200 px-3 text-sm text-red-700 transition hover:bg-red-50 disabled:cursor-wait disabled:opacity-60" onClick={removeAll} disabled={!rows.length || working}>
          <CheckCheck size={16} />
          Cancella tutte Anomalie
        </button>
      </div>
      {error && <p className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      <div className="grid gap-4">
        {grouped.map(([job, anomalies]) => (
          <section className="rounded-md border border-line" key={job}>
            <div className="border-b border-line bg-slate-50 px-3 py-2 text-sm font-semibold">{job}</div>
            <div className="grid gap-2 p-3">
              {anomalies.map((row) => (
                <div key={row.id} className="rounded-md border border-line p-3 text-sm">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge status={row.severita}>{row.severita}</Badge>
                      <strong>{row.tipo}</strong>
                      {row.cliente_nome && <span className="text-slate-500">{row.cliente_nome}</span>}
                      <span className="text-slate-500">{formatItalianDateTime(row.created_at)}</span>
                    </div>
                    <button className="inline-flex h-8 items-center gap-2 rounded-md border border-line px-2 text-xs transition hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60" onClick={() => removeOne(row.id)} disabled={working}>
                      <Trash2 size={14} />
                      Cancella vista
                    </button>
                  </div>
                  <p>{row.messaggio}</p>
                </div>
              ))}
            </div>
          </section>
        ))}
        {!rows.length && <div className="rounded-md border border-line bg-slate-50 p-4 text-sm text-slate-600">Nessuna anomalia aperta.</div>}
      </div>
    </Panel>
  );
}
