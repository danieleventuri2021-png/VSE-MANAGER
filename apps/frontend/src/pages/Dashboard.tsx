import { Database, Server, TriangleAlert } from "lucide-react";
import type React from "react";
import { Badge } from "../components/Badge";
import { Panel } from "../components/Panel";
import type { Job } from "../api/client";

export function Dashboard({ health, ports, jobs, onOpenAnomalies }: { health: any; ports: any; jobs: Job[]; onOpenAnomalies: () => void }) {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Panel title="Stato sistema">
        <div className="grid gap-3 sm:grid-cols-2">
          <Status icon={<Server size={20} />} label="Backend" value={health ? "raggiungibile" : "non raggiungibile"} status={health ? "certo" : "anomalia"} />
          <Status icon={<Database size={20} />} label="Database" value={health?.database ? "connesso" : "non connesso"} status={health?.database ? "certo" : "anomalia"} />
        </div>
      </Panel>
      <Panel title="Porte">
        <div className="space-y-3 text-sm">
          <Port label="Backend" status={ports?.backend} />
          <Port label="Frontend" status={ports?.frontend} />
        </div>
      </Panel>
      <Panel title="Anomalie aperte">
        <button className="flex w-full items-center gap-3 rounded-md p-2 text-left transition hover:bg-rose-50" onClick={onOpenAnomalies}>
          <TriangleAlert className="text-rose-600" size={24} />
          <div className="text-3xl font-semibold">{health?.open_anomalies ?? 0}</div>
        </button>
      </Panel>
      <div className="xl:col-span-3">
        <Panel title="Ultimi lavori">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr><th className="py-2">Titolo</th><th>Cliente</th><th>Stato</th><th>Righe</th><th>MTR</th></tr>
              </thead>
              <tbody>
                {jobs.slice(0, 8).map((job) => (
                  <tr key={job.id} className="border-t border-line">
                    <td className="py-2 font-medium">{job.titolo}</td>
                    <td>{job.cliente_nome || "-"}</td>
                    <td><Badge status={job.stato}>{job.stato}</Badge></td>
                    <td>{String(job.summary.excel_rows ?? "-")}</td>
                    <td>{String(job.summary.mtr_files ?? "-")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Status({ icon, label, value, status }: { icon: React.ReactNode; label: string; value: string; status: string }) {
  return <div className="flex items-center justify-between rounded-md border border-line p-3"><div className="flex items-center gap-2">{icon}<span>{label}</span></div><Badge status={status}>{value}</Badge></div>;
}

function Port({ label, status }: { label: string; status: any }) {
  return <div className="flex items-center justify-between"><span>{label} {status?.port}</span><Badge status={status?.free ? "certo" : "anomalia"}>{status?.free ? "libera" : `occupata ${status?.pid ? `PID ${status.pid}` : ""}`}</Badge></div>;
}
