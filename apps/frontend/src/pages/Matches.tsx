import { useCallback, useEffect, useState } from "react";
import { api, type Job } from "../api/client";
import { Badge } from "../components/Badge";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";

export function Matches({ jobs }: { jobs: Job[] }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

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
          <tbody>{rows.map((row, index) => <tr className="border-t border-line" key={index}><td className="py-2">{row.equipment?.row_index ?? "-"}</td><td>{row.equipment?.matricola || row.equipment?.seriale || row.mtr?.matricola || row.mtr?.seriale || "-"}</td><td>{row.equipment?.produttore || row.mtr?.produttore || "-"}</td><td>{row.equipment?.modello || row.mtr?.modello || "-"}</td><td>{row.mtr?.nome_file || "-"}</td><td><Badge status={row.status}>{row.status}</Badge></td><td>{row.score?.toFixed?.(1) ?? "-"}</td></tr>)}</tbody>
        </table>
        {!loading && jobId > 0 && rows.length === 0 && <p className="border-t border-line py-4 text-sm text-slate-500">Nessun abbinamento disponibile. Importa Excel/MTR/CSV e avvia Analizza per questo lavoro.</p>}
      </div>
    </Panel>
  );
}
