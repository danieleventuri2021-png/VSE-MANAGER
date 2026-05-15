import { LockKeyhole } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { login, type CurrentUser } from "../api/client";

export function Login({ onLogin }: { onLogin: (user: CurrentUser) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      onLogin(await login(username, password));
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Accesso non riuscito.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-slate-100 p-4">
      <form className="grid w-full max-w-sm gap-4 rounded-md border border-line bg-white p-5 shadow-sm" onSubmit={submit}>
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-md bg-action text-white"><LockKeyhole size={20} /></div>
          <div>
            <h1 className="text-lg font-semibold text-ink">Accesso VSE</h1>
            <p className="text-sm text-slate-500">Inserisci le credenziali utente</p>
          </div>
        </div>
        <label className="grid gap-1 text-sm font-medium text-slate-700">
          Utente
          <input className="h-10 rounded-md border border-line px-3 text-sm font-normal text-ink" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label className="grid gap-1 text-sm font-medium text-slate-700">
          Password
          <input className="h-10 rounded-md border border-line px-3 text-sm font-normal text-ink" value={password} onChange={(event) => setPassword(event.target.value)} type="password" autoComplete="current-password" autoFocus />
        </label>
        {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <button className="h-10 rounded-md bg-action px-4 text-sm font-medium text-white disabled:cursor-wait disabled:opacity-70" disabled={busy || !username || !password}>
          {busy ? "Accesso..." : "Entra"}
        </button>
      </form>
    </div>
  );
}
