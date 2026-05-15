import { KeyRound, Power, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { changePassword, createUser, deleteUser, listUsers, updateUser, type CurrentUser } from "../api/client";
import { Panel } from "../components/Panel";

export function Settings() {
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [form, setForm] = useState({ username: "", nome: "", password: "", ruolo: "operatore" });
  const [passwordForm, setPasswordForm] = useState({ old_password: "", new_password: "" });
  const [adminPasswords, setAdminPasswords] = useState<Record<number, string>>({});
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

  async function toggleUser(user: CurrentUser) {
    setMessage("");
    setError("");
    try {
      await updateUser(user.id, { attivo: !user.attivo });
      setMessage(user.attivo ? "Utente disabilitato" : "Utente riattivato");
      await loadUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Aggiornamento utente non riuscito.");
    }
  }

  async function resetUserPassword(user: CurrentUser) {
    const password = adminPasswords[user.id] || "";
    if (password.length < 6) return;
    setMessage("");
    setError("");
    try {
      await updateUser(user.id, { password });
      setAdminPasswords({ ...adminPasswords, [user.id]: "" });
      setMessage(`Password aggiornata per ${user.username}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Cambio password utente non riuscito.");
    }
  }

  async function removeUser(user: CurrentUser) {
    if (!window.confirm(`Cancellare l'utente ${user.username}?`)) return;
    setMessage("");
    setError("");
    try {
      await deleteUser(user.id);
      setMessage("Utente cancellato");
      await loadUsers();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Cancellazione utente non riuscita.");
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
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr><th className="py-2">Utente</th><th>Nome</th><th>Ruolo</th><th>Stato</th><th>Password</th><th className="text-right">Azioni</th></tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const lockedAdmin = user.username === "admin";
                  return (
                    <tr className="border-t border-line" key={user.id}>
                      <td className="py-2 font-medium">{user.username}</td>
                      <td>{user.nome || "-"}</td>
                      <td>{user.ruolo}</td>
                      <td><span className={`rounded-md px-2 py-1 text-xs ${user.attivo ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{user.attivo ? "attivo" : "disabilitato"}</span></td>
                      <td>
                        <div className="flex min-w-52 gap-2">
                          <input className="h-9 w-full rounded-md border border-line px-2 text-sm" placeholder="Nuova password" type="password" value={adminPasswords[user.id] || ""} onChange={(event) => setAdminPasswords({ ...adminPasswords, [user.id]: event.target.value })} />
                          <button className="inline-flex h-9 items-center rounded-md border border-line px-2 disabled:cursor-not-allowed disabled:opacity-60" title="Aggiorna password" onClick={() => resetUserPassword(user)} disabled={(adminPasswords[user.id] || "").length < 6}><KeyRound size={15} /></button>
                        </div>
                      </td>
                      <td>
                        <div className="flex justify-end gap-2">
                          <button className="inline-flex h-9 items-center gap-1 rounded-md border border-line px-2 text-xs disabled:cursor-not-allowed disabled:opacity-60" onClick={() => toggleUser(user)} disabled={lockedAdmin}><Power size={14} /> {user.attivo ? "Disabilita" : "Riattiva"}</button>
                          <button className="inline-flex h-9 items-center gap-1 rounded-md border border-red-200 px-2 text-xs text-red-700 disabled:cursor-not-allowed disabled:opacity-60" onClick={() => removeUser(user)} disabled={lockedAdmin}><Trash2 size={14} /> Cancella</button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
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
