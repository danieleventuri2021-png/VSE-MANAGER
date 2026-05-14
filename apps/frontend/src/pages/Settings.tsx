import { Panel } from "../components/Panel";

export function Settings() {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Panel title="Backend">
        <dl className="grid gap-2 text-sm">
          <Row label="API" value={import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"} />
          <Row label="Porta frontend" value={import.meta.env.VITE_FRONTEND_PORT || "5173"} />
        </dl>
      </Panel>
      <Panel title="Schema dati">
        <dl className="grid gap-2 text-sm">
          <Row label="Schema PostgreSQL" value="gestione_vse" />
          <Row label="Cartelle" value="data/input, data/output, data/backup, data/templates" />
        </dl>
      </Panel>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between gap-4 border-b border-line py-2"><dt className="font-medium">{label}</dt><dd className="text-right text-slate-600">{value}</dd></div>;
}
