import { Activity, AlertTriangle, ClipboardCheck, ClipboardList, Database, FileInput, FileText, Gauge, Link2, LogOut, Plus, Settings, ScrollText, SlidersHorizontal } from "lucide-react";
import type React from "react";
import type { CurrentUser } from "../api/client";

type View = "dashboard" | "jobs" | "new" | "import" | "matches" | "review" | "pdf" | "registry" | "job-settings" | "anomalies" | "logs" | "settings";

const items: { id: View; label: string; icon: React.ComponentType<{ size?: number }> }[] = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "jobs", label: "Lavori VSE", icon: ClipboardList },
  { id: "new", label: "Nuovo lavoro", icon: Plus },
  { id: "import", label: "Importazione", icon: FileInput },
  { id: "matches", label: "Abbinamenti", icon: Link2 },
  { id: "job-settings", label: "Impostazioni lavoro", icon: SlidersHorizontal },
  { id: "review", label: "Revisione MTR/CSV", icon: ClipboardCheck },
  { id: "pdf", label: "PDF", icon: FileText },
  { id: "registry", label: "Archivio", icon: Database },
  { id: "anomalies", label: "Anomalie", icon: AlertTriangle },
  { id: "logs", label: "Log operativo", icon: ScrollText },
  { id: "settings", label: "Impostazioni", icon: Settings },
];

export function Layout({ view, setView, user, onLogout, children }: { view: View; setView: (view: View) => void; user: CurrentUser; onLogout: () => void; children: React.ReactNode }) {
  return (
    <div className="min-h-screen lg:flex">
      <aside className="border-r border-line bg-white lg:w-64">
        <div className="flex h-16 items-center gap-3 border-b border-line px-5">
          <Activity className="text-action" size={24} />
          <div>
            <div className="text-sm font-semibold uppercase tracking-wide text-action">gestione-vse</div>
            <div className="text-xs text-slate-500">VSE / MTR/CSV locale</div>
          </div>
        </div>
        <nav className="grid gap-1 p-3">
          {items.map((item) => {
            const Icon = item.icon;
            const active = item.id === view;
            return (
              <button
                key={item.id}
                className={`flex h-10 items-center gap-3 rounded-md px-3 text-left text-sm ${active ? "bg-action text-white" : "text-slate-700 hover:bg-slate-100"}`}
                onClick={() => setView(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <main className="min-w-0 flex-1">
        <header className="flex h-16 items-center justify-between border-b border-line bg-white px-5">
          <div>
            <h1 className="text-lg font-semibold text-ink">Gestione verifiche elettriche</h1>
            <p className="text-xs text-slate-500">Import Excel, analisi MTR/CSV, anomalie e rinomina controllata</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-medium text-ink">{user.nome || user.username}</div>
              <div className="text-xs text-slate-500">{user.ruolo}</div>
            </div>
            <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm text-slate-700 hover:bg-slate-100" onClick={onLogout}>
              <LogOut size={16} /> Esci
            </button>
          </div>
        </header>
        <div className="p-5">{children}</div>
      </main>
    </div>
  );
}

export type { View };
