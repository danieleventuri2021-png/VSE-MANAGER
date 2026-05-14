import { useState } from "react";
import { api, type Job } from "../api/client";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";
import { formatItalianDateTime } from "../lib/date";

export function Logs({ jobs }: { jobs: Job[] }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (!jobId) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/api/jobs/${jobId}/logs`);
      setRows(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Panel title="Log operativo" action={<RefreshButton loading={loading} onClick={load} />}>
      <select className="mb-3 h-10 rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
        <option value={0}>Seleziona lavoro</option>
        {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
      </select>
      <div className="grid gap-2">
        {rows.map((row) => <div key={row.id} className="rounded-md border border-line bg-slate-50 p-3 text-sm"><div className="flex justify-between"><strong>{row.evento}</strong><span className="text-slate-500">{formatItalianDateTime(row.created_at)}</span></div><p className="mt-1">{row.messaggio}</p></div>)}
      </div>
    </Panel>
  );
}
