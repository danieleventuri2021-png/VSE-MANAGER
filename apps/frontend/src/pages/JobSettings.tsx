import { FileUp, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { saveJobSettings, uploadJobAsset, type Job } from "../api/client";
import { Panel } from "../components/Panel";

const fields = ["tecnico", "firma_path", "proprieta", "periodicita", "tensione", "frequenza", "protezione", "template_pdf", "intestazione_pdf"];
const periodicitaOptions = [{ value: "12 mesi", label: "12 mesi" }, { value: "24 mesi", label: "24 mesi" }];
const protezioneOptions = [
  { value: "Magnetotermico", label: "Magnetotermico" },
  { value: "Magnetotermico Differenziale", label: "Magnetotermico Differenziale" },
  { value: "Termico", label: "Termico" },
  { value: "Trasformatore di isolamento", label: "Trasformatore di isolamento" },
  { value: "Fusibili", label: "Fusibili" },
  { value: "Altro", label: "Altro" },
];

export function JobSettings({ jobs, onDone }: { jobs: Job[]; onDone: () => void }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const job = jobs.find((item) => item.id === jobId);
  const [values, setValues] = useState<Record<string, string>>({});
  const [uploadingField, setUploadingField] = useState("");

  useEffect(() => {
    if (jobId) loadJob(jobId);
  }, [jobs]);

  function loadJob(id: number) {
    const selected = jobs.find((item) => item.id === id);
    setJobId(id);
    setValues({
      tecnico: selected?.tecnico_default || "",
      firma_path: selected?.firma_default_path || "",
      proprieta: selected?.proprieta_default || "",
      periodicita: normalizePeriodicity(selected?.periodicita_default),
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

  async function chooseFile(field: string, file: File | null) {
    if (!jobId || !file || !isFileField(field)) return;
    setUploadingField(field);
    try {
      const updated = await uploadJobAsset(jobId, field, file);
      setValues({
        ...values,
        firma_path: updated.firma_default_path || values.firma_path || "",
        template_pdf: updated.template_pdf || values.template_pdf || "",
        intestazione_pdf: updated.intestazione_pdf || values.intestazione_pdf || "",
      });
      onDone();
    } finally {
      setUploadingField("");
    }
  }

  return (
    <Panel title="Impostazioni lavoro" action={<button className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-sm text-white" onClick={save}><Save size={16} /> Salva</button>}>
      <select className="mb-4 h-10 rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => loadJob(Number(event.target.value))}>
        <option value={0}>Seleziona lavoro</option>
        {jobs.map((item) => <option key={item.id} value={item.id}>{item.id} - {item.titolo}</option>)}
      </select>
      {job && <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{fields.map((field) => <FieldControl key={field} field={field} value={values[field] ?? ""} uploading={uploadingField === field} onChange={(value) => setValues({ ...values, [field]: value })} onFile={(file) => chooseFile(field, file)} />)}</div>}
    </Panel>
  );
}

function FieldControl({ field, value, uploading, onChange, onFile }: { field: string; value: string; uploading: boolean; onChange: (value: string) => void; onFile: (file: File | null) => void }) {
  return (
    <label className="grid gap-1 text-xs font-medium uppercase text-slate-500">
      {field.replaceAll("_", " ")}
      {field === "periodicita" ? (
        <select className="h-10 rounded-md border border-line px-3 text-sm normal-case text-ink" value={value || "12 mesi"} onChange={(event) => onChange(event.target.value)}>
          {periodicitaOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      ) : field === "protezione" ? (
        <select className="h-10 rounded-md border border-line px-3 text-sm normal-case text-ink" value={value || "Trasformatore di isolamento"} onChange={(event) => onChange(event.target.value)}>
          {protezioneOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      ) : isFileField(field) ? (
        <div className="flex gap-2">
          <input className="h-10 min-w-0 flex-1 rounded-md border border-line px-3 text-sm normal-case text-ink" value={value} onChange={(event) => onChange(event.target.value)} />
          <span className="relative inline-flex">
            <input className="absolute inset-0 cursor-pointer opacity-0" type="file" accept={acceptFor(field)} onChange={(event) => onFile(event.target.files?.[0] ?? null)} disabled={uploading} />
            <button className="inline-flex h-10 items-center gap-2 rounded-md border border-line px-3 text-sm normal-case text-ink disabled:cursor-wait disabled:opacity-60" type="button" disabled={uploading}><FileUp size={16} /> {uploading ? "Carico..." : "Scegli file"}</button>
          </span>
        </div>
      ) : (
        <input className="h-10 rounded-md border border-line px-3 text-sm normal-case text-ink" value={value} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  );
}

function normalizePeriodicity(value?: string | null) {
  const text = String(value || "").trim();
  if (text === "24") return "24 mesi";
  if (text === "12") return "12 mesi";
  return text || "12 mesi";
}

function isFileField(field: string): field is "firma_path" | "template_pdf" | "intestazione_pdf" {
  return field === "firma_path" || field === "template_pdf" || field === "intestazione_pdf";
}

function acceptFor(field: string) {
  if (field === "template_pdf") return ".pdf,application/pdf";
  return ".png,.jpg,.jpeg,image/png,image/jpeg";
}
