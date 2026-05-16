import { Fragment, useCallback, useEffect, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, GitCompare } from "lucide-react";
import { api, type Job } from "../api/client";
import { Badge } from "../components/Badge";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";

export function Matches({ jobs }: { jobs: Job[] }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [openRow, setOpenRow] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/api/jobs/${jobId}/matches`);
      setRows(data);
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    setRows([]);
    setOpenRow(null);
    load();
  }, [load]);

  return (
    <Panel title="Abbinamenti" action={<RefreshButton loading={loading} onClick={load} />}>
      <div className="mb-3">
        <select className="h-10 rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
          <option value={0}>Seleziona lavoro</option>
          {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Riga</th><th>Matricola</th><th>Produttore</th><th>Modello</th><th>MTR/CSV</th><th>Stato</th><th>Score</th></tr></thead>
          <tbody>
            {rows.map((row, index) => {
              const expandable = row.status !== "certo" || row.differences?.fields?.length > 0;
              const opened = openRow === index;
              return (
                <Fragment key={index}>
                  <tr className={`border-t border-line ${expandable ? "cursor-pointer hover:bg-slate-50" : ""}`} onClick={() => expandable && setOpenRow(opened ? null : index)}>
                    <td className="py-2">
                      <span className="inline-flex items-center gap-1">
                        {expandable ? opened ? <ChevronDown size={15} /> : <ChevronRight size={15} /> : <span className="w-[15px]" />}
                        {row.equipment?.row_index ?? "-"}
                      </span>
                    </td>
                    <td>{row.equipment?.matricola || row.equipment?.seriale || row.mtr?.matricola || row.mtr?.seriale || "-"}</td>
                    <td>{row.equipment?.produttore || row.mtr?.produttore || "-"}</td>
                    <td>{row.equipment?.modello || row.mtr?.modello || "-"}</td>
                    <td>{row.mtr?.nome_file || "-"}</td>
                    <td><Badge status={row.status}>{row.status}</Badge></td>
                    <td>{row.score?.toFixed?.(1) ?? "-"}</td>
                  </tr>
                  {opened && <tr className="border-t border-line bg-slate-50"><td colSpan={7}><MatchDetail row={row} /></td></tr>}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {!loading && jobId > 0 && rows.length === 0 && <p className="border-t border-line py-4 text-sm text-slate-500">Nessun abbinamento disponibile. Importa Excel/MTR/CSV e avvia Analizza per questo lavoro.</p>}
      </div>
    </Panel>
  );
}

function MatchDetail({ row }: { row: any }) {
  const fields = row.differences?.fields || [];
  return (
    <div className="grid gap-3 p-3 text-sm">
      <div className="flex items-center gap-2 text-slate-700">
        <GitCompare size={16} />
        <span className="font-medium">{row.reason || "Dettaglio abbinamento"}</span>
      </div>
      {row.status === "mancante" && <Notice text="Questa riga Excel non ha un file MTR/CSV associato con sufficiente confidenza." />}
      {row.status === "mtr_orfano" && <Notice text="Questo file MTR/CSV non è stato collegato ad alcuna riga Excel." />}
      {fields.length > 0 ? (
        <div className="overflow-x-auto rounded-md border border-line bg-white">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100 uppercase text-slate-500"><tr><th className="p-2">Campo</th><th>Excel</th><th>MTR/CSV</th></tr></thead>
            <tbody>
              {fields.map((field: any) => (
                <tr className="border-t border-line" key={field.field}>
                  <td className="p-2 font-medium">{field.field}</td>
                  <td className="pr-2">{field.excel || "-"}</td>
                  <td>{field.mtr || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-2 rounded-md border border-line bg-white p-3 sm:grid-cols-2">
          <DataBlock title="Excel" data={row.equipment} />
          <DataBlock title="MTR/CSV" data={row.mtr} />
        </div>
      )}
    </div>
  );
}

function Notice({ text }: { text: string }) {
  return <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-amber-800"><AlertTriangle size={16} /> {text}</div>;
}

function DataBlock({ title, data }: { title: string; data: any }) {
  const fields = ["matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto"];
  return (
    <div>
      <div className="mb-2 font-medium text-slate-700">{title}</div>
      <dl className="grid gap-1">
        {fields.map((field) => <div className="grid grid-cols-3 gap-2" key={field}><dt className="text-slate-500">{field}</dt><dd className="col-span-2 break-words">{data?.[field] || "-"}</dd></div>)}
      </dl>
    </div>
  );
}
