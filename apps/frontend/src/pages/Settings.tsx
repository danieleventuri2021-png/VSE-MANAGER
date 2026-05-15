import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { changePassword, createUser, listUsers, type CurrentUser } from "../api/client";
import { Panel } from "../components/Panel";

export function Settings() {
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [form, setForm] = useState({ username: "", nome: "", password: "", ruolo: "operatore" });
  const [passwordForm, setPasswordForm] = useState({ old_password: "", new_password: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadUsers() {
    try {
      setUsers(await listUsers());
    } catch {
      setUsers([]);
    }
  }

  async function saveUser() {
    setMessage("");
    setError("");
    try {
      await createUser(form);
      setForm({ username: "", nome: "", password: "", ruolo: "operatore" });
      setMessage("Utente creato");
      await loadUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Creazione utente non riuscita.");
    }
  }

  async function savePassword() {
    setMessage("");
    setError("");
    try {
      await changePassword(passwordForm);
      setPasswordForm({ old_password: "", new_password: "" });
      setMessage("Password aggiornata");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Cambio password non riuscito.");
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

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
      <Panel title="Utenti">
        <div className="grid gap-3">
          <div className="grid gap-2 text-sm">
            {users.map((user) => <Row key={user.id} label={user.username} value={`${user.nome || "-"} - ${user.ruolo}`} />)}
            {!users.length && <p className="text-sm text-slate-500">Nessun utente visibile.</p>}
          </div>
          <div className="grid gap-2 border-t border-line pt-3 md:grid-cols-2">
            <input className="h-10 rounded-md border border-line px-3 text-sm" placeholder="Username" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
            <input className="h-10 rounded-md border border-line px-3 text-sm" placeholder="Nome" value={form.nome} onChange={(event) => setForm({ ...form, nome: event.target.value })} />
            <input className="h-10 rounded-md border border-line px-3 text-sm" placeholder="Password" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
            <select className="h-10 rounded-md border border-line px-3 text-sm" value={form.ruolo} onChange={(event) => setForm({ ...form, ruolo: event.target.value })}>
              <option value="operatore">operatore</option>
              <option value="admin">admin</option>
            </select>
          </div>
          {message && <p className="text-sm text-action">{message}</p>}
          {error && <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-3 text-sm text-white disabled:opacity-60" onClick={saveUser} disabled={!form.username || !form.password}><Save size={16} /> Crea utente</button>
        </div>
      </Panel>
      <Panel title="Password">
        <div className="grid gap-3">
          <input className="h-10 rounded-md border border-line px-3 text-sm" placeholder="Password attuale" type="password" value={passwordForm.old_password} onChange={(event) => setPasswordForm({ ...passwordForm, old_password: event.target.value })} />
          <input className="h-10 rounded-md border border-line px-3 text-sm" placeholder="Nuova password" type="password" value={passwordForm.new_password} onChange={(event) => setPasswordForm({ ...passwordForm, new_password: event.target.value })} />
          <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-3 text-sm text-white disabled:opacity-60" onClick={savePassword} disabled={!passwordForm.old_password || passwordForm.new_password.length < 6}><Save size={16} /> Cambia password</button>
        </div>
      </Panel>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between gap-4 border-b border-line py-2"><dt className="font-medium">{label}</dt><dd className="text-right text-slate-600">{value}</dd></div>;
}
