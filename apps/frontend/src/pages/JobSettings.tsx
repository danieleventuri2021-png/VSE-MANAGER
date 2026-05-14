import { Save } from "lucide-react";
import { useState } from "react";
import { saveJobSettings, type Job } from "../api/client";
import { Panel } from "../components/Panel";

const fields = ["tecnico", "firma_path", "proprieta", "periodicita", "tensione", "frequenza", "protezione", "template_pdf", "intestazione_pdf"];

export function JobSettings({ jobs, onDone }: { jobs: Job[]; onDone: () => void }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const job = jobs.find((item) => item.id === jobId);
  const [values, setValues] = useState<Record<string, string>>({});

  function loadJob(id: number) {
    const selected = jobs.find((item) => item.id === id);
    setJobId(id);
    setValues({
      tecnico: selected?.tecnico_default || "",
      firma_path: selected?.firma_default_path || "",
      proprieta: selected?.proprieta_default || "",
      periodicita: selected?.periodicita_default || "12",
      tensione: selected?.tensione_default || "220",
      frequenza: selected?.frequenza_default || "50",
      protezione: selected?.protezione_default || "Trasformatore di isolamento",
      template_pdf: selected?.template_pdf || "standard",
      intestazione_pdf: selected?.intestazione_pdf || "standard",
    });
  }

  async function save() {
    if (!jobId) return;
    await saveJobSettings(jobId, values);
    onDone();
  }

  return (
    <Panel title="Impostazioni lavoro" action={<button className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-sm text-white" onClick={save}><Save size={16} /> Salva</button>}>
      <select className="mb-4 h-10 rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => loadJob(Number(event.target.value))}>
        <option value={0}>Seleziona lavoro</option>
        {jobs.map((item) => <option key={item.id} value={item.id}>{item.id} - {item.titolo}</option>)}
      </select>
      {job && <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{fields.map((field) => <label key={field} className="grid gap-1 text-xs font-medium uppercase text-slate-500">{field.replaceAll("_", " ")}<input className="h-10 rounded-md border border-line px-3 text-sm normal-case text-ink" value={values[field] ?? ""} onChange={(event) => setValues({ ...values, [field]: event.target.value })} /></label>)}</div>}
    </Panel>
  );
}
