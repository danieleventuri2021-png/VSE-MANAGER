import { Save } from "lucide-react";
import { useState } from "react";
import type React from "react";
import { createJob } from "../api/client";
import { Panel } from "../components/Panel";

export function NewJob({ onCreated }: { onCreated: () => void }) {
  const [titolo, setTitolo] = useState("");
  const [cliente, setCliente] = useState("");
  const [folder, setFolder] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const job = await createJob({ titolo, cliente_nome: cliente || undefined, mtr_folder: folder || undefined });
      setMessage(`Lavoro ${job.id} creato`);
      setTitolo("");
      setCliente("");
      setFolder("");
      onCreated();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "Creazione lavoro non riuscita.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Panel title="Nuovo lavoro">
      <form className="grid max-w-3xl gap-4" onSubmit={submit}>
        <Field label="Titolo" value={titolo} onChange={setTitolo} required />
        <Field label="Cliente" value={cliente} onChange={setCliente} />
        <Field label="Cartella MTR" value={folder} onChange={setFolder} />
        <button className="inline-flex h-10 w-fit items-center gap-2 rounded-md bg-action px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60" type="submit" disabled={submitting}><Save size={18} /> {submitting ? "Creazione..." : "Crea lavoro"}</button>
        {message && <p className="text-sm text-action">{message}</p>}
        {error && <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      </form>
    </Panel>
  );
}

function Field({ label, value, onChange, required }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return <label className="grid gap-1 text-sm"><span className="font-medium">{label}</span><input className="h-10 rounded-md border border-line px-3" value={value} required={required} onChange={(event) => onChange(event.target.value)} /></label>;
}
