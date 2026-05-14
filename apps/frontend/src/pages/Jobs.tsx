import { Badge } from "../components/Badge";
import { Panel } from "../components/Panel";
import type { Job } from "../api/client";
import { formatItalianDateTime } from "../lib/date";

export function Jobs({ jobs }: { jobs: Job[] }) {
  return (
    <Panel title="Lavori VSE">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr><th className="py-2">ID</th><th>Titolo</th><th>Cliente</th><th>Stato</th><th>Excel</th><th>Cartella MTR</th><th>Aggiornato</th></tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id} className="border-t border-line">
                <td className="py-2">{job.id}</td>
                <td className="font-medium">{job.titolo}</td>
                <td>{job.cliente_nome || "-"}</td>
                <td><Badge status={job.stato}>{job.stato}</Badge></td>
                <td className="max-w-52 truncate">{job.excel_path || "-"}</td>
                <td className="max-w-52 truncate">{job.mtr_folder || "-"}</td>
                <td>{formatItalianDateTime(job.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
