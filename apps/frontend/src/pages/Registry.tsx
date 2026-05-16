import { Activity, ArrowUpDown, Calendar, ListChecks, LoaderCircle, Search, Trash2, UploadCloud, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, deleteRegistryEquipment, getRegistryMeasurements, getRegistryTrend, listRegistryClients, listRegistryEquipment, syncRegistry, type Job } from "../api/client";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";
import { formatItalianDate } from "../lib/date";

const columns = [
  { key: "cliente_nome", label: "Cliente" },
  { key: "tipologia", label: "Tipologia" },
  { key: "produttore", label: "Marca" },
  { key: "modello", label: "Modello" },
  { key: "matricola", label: "Matricola" },
  { key: "inventario_gestionale", label: "INVGEST" },
  { key: "ubicazione", label: "Ubicazione" },
  { key: "data_ultima_verifica", label: "Ultima VSE" },
  { key: "data_prossima_verifica", label: "Prossima VSE" },
];

export function Registry({ jobs }: { jobs: Job[] }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [cliente, setCliente] = useState("");
  const [clients, setClients] = useState<string[]>([]);
  const [rows, setRows] = useState<any[]>([]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" }>({ key: "cliente_nome", dir: "asc" });
  const [report, setReport] = useState<any>(null);
  const [modal, setModal] = useState<{ title: string; type: "measurements" | "trend"; data: any } | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      setRows(await listRegistryEquipment(cliente ? { cliente } : undefined));
      setClients(await listRegistryClients());
      setSelectedIds([]);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Caricamento archivio non riuscito.");
    } finally {
      setLoading(false);
    }
  }

  async function sync() {
    if (!jobId) return;
    setSyncing(true);
    setError("");
    try {
      const data = await syncRegistry(jobId);
      setReport(data);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Sincronizzazione archivio non riuscita.");
    } finally {
      setSyncing(false);
    }
  }

  function calendarUrl() {
    const base = `${api.defaults.baseURL}/api/registry/calendar.ics`;
    return cliente ? `${base}?cliente=${encodeURIComponent(cliente)}` : base;
  }

  const sortBy = useCallback((key: string) => {
    setSort((current) => ({ key, dir: current.key === key && current.dir === "asc" ? "desc" : "asc" }));
  }, []);

  const handleFilterChange = useCallback((key: string, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  }, []);

  const displayedRows = useMemo(() => {
    const filtered = rows.filter((row) =>
      columns.every((column) => {
        const needle = (filters[column.key] || "").trim().toLowerCase();
        if (!needle) return true;
        const value = row[column.key];
        return String(value || "").toLowerCase().includes(needle);
      }),
    );
    return [...filtered].sort((a, b) => {
      const left = String(a[sort.key] || "").toLowerCase();
      const right = String(b[sort.key] || "").toLowerCase();
      return sort.dir === "asc" ? left.localeCompare(right) : right.localeCompare(left);
    });
  }, [rows, filters, sort]);

  const selectedDisplayed = displayedRows.filter((row) => selectedIds.includes(row.id)).length;

  async function openMeasurements(row: any) {
    setError("");
    try {
      const data = await getRegistryMeasurements(row.id);
      setModal({ title: `Misure - ${row.tipologia || row.modello || row.identificativo}`, type: "measurements", data });
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Lettura misure non riuscita.");
    }
  }

  async function openTrend(row: any) {
    setError("");
    try {
      const data = await getRegistryTrend(row.id);
      setModal({ title: `Trend - ${row.tipologia || row.modello || row.identificativo}`, type: "trend", data });
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Lettura trend non riuscita.");
    }
  }

  function toggleRow(id: number) {
    setSelectedIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function toggleDisplayed(checked: boolean) {
    const ids = displayedRows.map((row) => row.id);
    setSelectedIds((current) => checked ? Array.from(new Set([...current, ...ids])) : current.filter((id) => !ids.includes(id)));
  }

  async function removeSelected() {
    if (!selectedIds.length) return;
    const first = window.confirm(`Eliminare ${selectedIds.length} apparecchiature dall'archivio?`);
    if (!first) return;
    const expected = `ELIMINA ${selectedIds.length} ARCHIVIO`;
    const typed = window.prompt(`Conferma definitiva: digita ${expected}`);
    if (typed !== expected) return;
    try {
      await deleteRegistryEquipment(selectedIds, typed);
      await load();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Cancellazione archivio non riuscita.");
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <div className="grid gap-4">
      <Panel title="Archivio apparecchiature" action={<RefreshButton loading={loading} onClick={load} />}>
        <div className="flex flex-wrap gap-3">
          <select className="h-10 rounded-md border border-line px-3 text-sm" value={cliente} onChange={(event) => setCliente(event.target.value)}>
            <option value="">Tutti i clienti</option>
            {clients.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
          <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={load}>Filtra cliente</button>
          <select className="h-10 rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
            <option value={0}>Lavoro per aggiornare archivio</option>
            {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
          </select>
          <button className="inline-flex h-10 items-center gap-2 rounded-md bg-action px-3 text-sm text-white disabled:cursor-wait disabled:opacity-70" onClick={sync} disabled={syncing}>{syncing ? <LoaderCircle size={16} className="animate-spin" /> : <UploadCloud size={16} />} {syncing ? "Aggiorno archivio..." : "Aggiorna archivio da lavoro"}</button>
          <a className="inline-flex h-10 items-center gap-2 rounded-md border border-line px-3 text-sm" href={calendarUrl()}><Calendar size={16} /> Esporta Google Calendar</a>
          <button className="inline-flex h-10 items-center gap-2 rounded-md border border-red-200 px-3 text-sm text-red-700 disabled:cursor-not-allowed disabled:opacity-50" onClick={removeSelected} disabled={!selectedIds.length}><Trash2 size={16} /> Elimina selezionati ({selectedIds.length})</button>
        </div>
        {error && <p className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        {report && <pre className="mt-4 overflow-auto rounded-md bg-slate-900 p-3 text-xs text-white">{JSON.stringify(report, null, 2)}</pre>}
      </Panel>
      <Panel title={`Apparecchiature (${displayedRows.length})`}>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="w-10 py-2 pr-2 align-top">
                  <input type="checkbox" checked={displayedRows.length > 0 && selectedDisplayed === displayedRows.length} onChange={(event) => toggleDisplayed(event.target.checked)} />
                </th>
                {columns.map((column) => (
                  <th className="min-w-32 py-2 pr-2 align-top" key={column.key}>
                    <button className="mb-2 inline-flex items-center gap-1 font-semibold uppercase" onClick={() => sortBy(column.key)}>{column.label}<ArrowUpDown size={13} /></button>
                    <label className="flex h-8 items-center gap-1 rounded-md border border-line bg-white px-2 normal-case"><Search size={12} /><input className="w-full text-xs outline-none" value={filters[column.key] || ""} onChange={(event) => handleFilterChange(column.key, event.target.value)} placeholder="Cerca" /></label>
                  </th>
                ))}
                <th className="py-2">Azioni</th>
              </tr>
            </thead>
            <tbody>
              {displayedRows.map((row) => <tr className="border-t border-line" key={row.id}><td className="py-2"><input type="checkbox" checked={selectedIds.includes(row.id)} onChange={() => toggleRow(row.id)} /></td><td>{row.cliente_nome}</td><td>{row.tipologia || "-"}</td><td>{row.produttore || "-"}</td><td>{row.modello || "-"}</td><td>{row.matricola || "-"}</td><td>{row.inventario_gestionale || "-"}</td><td>{row.ubicazione || row.reparto || "-"}</td><td>{formatItalianDate(row.data_ultima_verifica)}</td><td>{formatItalianDate(row.data_prossima_verifica)}</td><td><div className="flex gap-1"><button className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line" title="Valori misurati" onClick={() => openMeasurements(row)}><ListChecks size={16} /></button><button className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line" title="Trend misure" onClick={() => openTrend(row)}><Activity size={16} /></button></div></td></tr>)}
            </tbody>
          </table>
        </div>
      </Panel>
      {modal && <RegistryModal modal={modal} onClose={() => setModal(null)} />}
    </div>
  );
}

function RegistryModal({ modal, onClose }: { modal: { title: string; type: "measurements" | "trend"; data: any }; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4">
      <div className="max-h-[85vh] w-full max-w-5xl overflow-hidden rounded-md bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h3 className="text-sm font-semibold">{modal.title}</h3>
          <button className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line" onClick={onClose}><X size={16} /></button>
        </div>
        <div className="max-h-[75vh] overflow-auto p-4">
          {modal.type === "measurements" ? <MeasurementsTable rows={modal.data.measurements || []} /> : <TrendView series={modal.data.series || []} />}
        </div>
      </div>
    </div>
  );
}

function MeasurementsTable({ rows }: { rows: any[] }) {
  if (!rows.length) return <p className="text-sm text-slate-500">Nessuna misura disponibile.</p>;
  return <table className="w-full text-left text-sm"><thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Misura</th><th>Valore</th><th>Unita</th><th>Esito</th></tr></thead><tbody>{rows.map((row, index) => <tr className="border-t border-line" key={`${row.name}-${index}`}><td className="py-2">{row.name}</td><td>{row.value}</td><td>{row.unit || "-"}</td><td>{row.status || "-"}</td></tr>)}</tbody></table>;
}

function TrendView({ series }: { series: any[] }) {
  const visible = series.filter((item) => item.points?.length);
  if (!visible.length) return <p className="text-sm text-slate-500">Nessun trend numerico disponibile.</p>;
  return <div className="grid gap-4 lg:grid-cols-2">{visible.map((item) => <TrendCard key={item.name} item={item} />)}</div>;
}

function TrendCard({ item }: { item: any }) {
  const points = item.points || [];
  const values = points.map((point: any) => Number(point.value));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const polyline = points.map((point: any, index: number) => `${(index / Math.max(points.length - 1, 1)) * 300},${90 - ((Number(point.value) - min) / span) * 70}`).join(" ");
  return (
    <div className="rounded-md border border-line p-3">
      <div className="mb-2 text-sm font-semibold">{item.name}</div>
      <svg viewBox="0 0 300 100" className="h-32 w-full overflow-visible">
        <polyline points={polyline} fill="none" stroke="#0f766e" strokeWidth="3" />
        {points.map((point: any, index: number) => <circle key={`${point.date}-${index}`} cx={(index / Math.max(points.length - 1, 1)) * 300} cy={90 - ((Number(point.value) - min) / span) * 70} r="3" fill="#0f766e" />)}
      </svg>
      <div className="grid gap-1 text-xs text-slate-600">{points.map((point: any, index: number) => <div className="flex justify-between gap-2" key={`${point.date}-${index}`}><span>{formatItalianDate(point.date)}</span><span>{point.value} {point.unit}</span></div>)}</div>
    </div>
  );
}
