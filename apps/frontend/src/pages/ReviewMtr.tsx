import { FileCheck, Save, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { applyJobDefaults, generateOnePdf, getReview, getReviewDetail, saveJobSettings, saveReview, saveSource, type Job } from "../api/client";
import { Badge } from "../components/Badge";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";

const fieldGroups = [
  { title: "Dati identificativi", fields: ["tipologia", "manufacturer", "model", "serial", "civab", "proprieta", "invGest", "invEnte", "presidio", "reparto", "stanza", "periodicita", "classe", "apType"] },
  { title: "Dati tecnici", fields: ["installazione", "mobilita", "tensione", "frequenza", "potenza", "potenza_unit", "protezione", "fusibili_conformita", "dati_targa_fusibili", "valore_nominale", "protezione_altro"] },
  { title: "Esame a vista", fields: ["vista_targa", "vista_telaio", "vista_parti_mov", "vista_cavo", "vista_passacavo", "vista_spie", "vista_parti_appl", "vista_doc"] },
  { title: "Tecnico, misure ed esito", fields: ["tecnico", "firma_path", "earthResPos", "funz_accensione", "funz_codice_prot", "funz_normativa", "funz_prova_part", "overallStatus", "note"] },
];
const editableFields = fieldGroups.flatMap((group) => group.fields);

const options: Record<string, { value: string; label: string }[]> = {
  periodicita: [{ value: "12 mesi", label: "12 mesi" }, { value: "24 mesi", label: "24 mesi" }],
  classe: [{ value: "I", label: "I" }, { value: "II", label: "II" }, { value: "AI", label: "AI" }],
  apType: [{ value: "B", label: "B" }, { value: "BF", label: "BF" }, { value: "CF", label: "CF" }],
  installazione: [{ value: "Permanente", label: "Permanente" }, { value: "Non permanente", label: "Non permanente" }],
  mobilita: [{ value: "Fisso", label: "Fisso" }, { value: "Spostabile", label: "Spostabile" }, { value: "Trasportabile", label: "Trasportabile" }, { value: "Portatile", label: "Portatile" }, { value: "Stazionario", label: "Stazionario" }],
  potenza_unit: [{ value: "W", label: "W" }, { value: "A", label: "A" }, { value: "VA", label: "VA" }],
  protezione: [{ value: "Magnetotermico", label: "Magnetotermico" }, { value: "Magnetotermico Differenziale", label: "Magnetotermico Differenziale" }, { value: "Termico", label: "Termico" }, { value: "Trasformatore di isolamento", label: "Trasformatore di isolamento" }, { value: "Fusibili", label: "Fusibili" }, { value: "Altro", label: "Altro" }],
  fusibili_conformita: [{ value: "", label: "-" }, { value: "conformi", label: "conformi ai dati di targa" }, { value: "non conformi", label: "non conformi ai dati di targa" }, { value: "senza dati", label: "senza dati di targa" }],
  vista_targa: visualOptions(),
  vista_telaio: visualOptions(),
  vista_parti_mov: visualOptions(),
  vista_cavo: visualOptions(),
  vista_passacavo: visualOptions(),
  vista_spie: visualOptions(),
  vista_parti_appl: visualOptions(),
  vista_doc: visualOptions(),
  funz_accensione: [{ value: "", label: "-" }, ...visualOptions()],
  funz_prova_part: [{ value: "", label: "-" }, ...visualOptions()],
  overallStatus: [{ value: "Positivo", label: "Positivo" }, { value: "Negativo", label: "Negativo" }, { value: "Da revisionare", label: "Apparecchiatura da revisionare / necessita manutenzione" }],
};

function visualOptions() {
  return [{ value: "OK", label: "OK" }, { value: "KO", label: "NO OK" }, { value: "NA", label: "NA" }];
}

export function ReviewMtr({ jobs }: { jobs: Job[] }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [items, setItems] = useState<any[]>([]);
  const [selected, setSelected] = useState<number>(0);
  const [detail, setDetail] = useState<any>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [loadingList, setLoadingList] = useState(false);

  async function loadList() {
    if (!jobId) return;
    setLoadingList(true);
    try {
      const data = await getReview(jobId);
      setItems(data);
      if (!selected && data[0]) setSelected(data[0].file_mtr_id);
    } finally {
      setLoadingList(false);
    }
  }

  async function loadDetail(fileId = selected) {
    if (!jobId || !fileId) return;
    const data = await getReviewDetail(jobId, fileId);
    setDetail(data);
    setFields(Object.fromEntries(editableFields.map((field) => [field, data.final?.[field] ?? defaultValue(field)])));
  }

  async function save() {
    if (!jobId || !selected) return;
    await saveReview(jobId, selected, { dati_revisionati: fields, stato_revisione: "revisionato" });
    setMessage("Revisione salvata");
    await loadDetail();
  }

  async function applyDefaults() {
    if (!jobId) return;
    await applyJobDefaults(jobId, { values: fields });
    setMessage("Valori comuni applicati agli MTR non bloccati");
    await loadDetail();
  }

  async function saveAsJobDefaults() {
    if (!jobId) return;
    await saveJobSettings(jobId, {
      tecnico: fields.tecnico,
      firma_path: fields.firma_path,
      proprieta: fields.proprieta,
      periodicita: fields.periodicita,
      tensione: fields.tensione,
      frequenza: fields.frequenza,
      protezione: fields.protezione,
    });
    setMessage("Valori comuni salvati come default lavoro");
  }

  useEffect(() => { loadList(); }, [jobId]);
  useEffect(() => { loadDetail(); }, [selected]);

  return (
    <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
      <Panel title="MTR del lavoro" action={<RefreshButton loading={loadingList} onClick={loadList} />}>
        <select className="mb-3 h-10 w-full rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
          <option value={0}>Seleziona lavoro</option>
          {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
        </select>
        <div className="grid gap-2">
          {items.map((item) => (
            <button key={item.file_mtr_id} className={`rounded-md border p-3 text-left text-sm ${selected === item.file_mtr_id ? "border-action bg-blue-50" : "border-line bg-white"}`} onClick={() => setSelected(item.file_mtr_id)}>
              <div className="font-medium">{item.nome_file}</div>
              <div className="mt-1 flex gap-2"><Badge status={item.stato_revisione}>{item.stato_revisione}</Badge>{item.is_permanent_three_measure_template && <Badge status="certo">permanente 3 PE</Badge>}</div>
            </button>
          ))}
        </div>
      </Panel>
      <div className="grid gap-4">
        {message && <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}
        {detail && (
          <>
            <Panel title="Revisione MTR - campi modulo VSS.GEN" action={<div className="flex flex-wrap gap-2"><button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={saveAsJobDefaults}>Salva default lavoro</button><button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={applyDefaults}><ShieldCheck size={16} /> Applica a tutti</button><button className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-sm text-white" onClick={save}><Save size={16} /> Applica solo a questo MTR</button></div>}>
              <div className="grid gap-5">
                {fieldGroups.map((group) => (
                  <section key={group.title}>
                    <h3 className="mb-2 text-sm font-semibold text-ink">{group.title}</h3>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {group.fields.map((field) => <FieldControl key={field} field={field} value={fields[field] ?? defaultValue(field)} onChange={(value) => setFields({ ...fields, [field]: value })} />)}
                    </div>
                  </section>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={() => saveSource(selected, { fields })}>Salva nel sorgente MTR/CSV</button>
                <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={() => generateOnePdf(jobId, selected)}><FileCheck size={16} /> Genera PDF singolo</button>
              </div>
            </Panel>
            <Panel title="Dati sorgente, Excel e finali">
              <div className="grid gap-4 lg:grid-cols-3">
                <DataBlock title="MTR / Ansur" data={detail.source} />
                <DataBlock title="Excel associato" data={detail.excel} />
                <DataBlock title="Finale PDF" data={detail.final} badges={detail.badges} />
              </div>
            </Panel>
          </>
        )}
      </div>
    </div>
  );
}

function FieldControl({ field, value, onChange }: { field: string; value: string; onChange: (value: string) => void }) {
  const fieldOptions = options[field];
  return (
    <label className="grid gap-1 text-xs font-medium uppercase text-slate-500">
      {labelFor(field)}
      {fieldOptions ? (
        <select className="h-10 rounded-md border border-line px-3 text-sm normal-case text-ink" value={value} onChange={(event) => onChange(event.target.value)}>
          {fieldOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      ) : (
        <input className="h-10 rounded-md border border-line px-3 text-sm normal-case text-ink" value={value} onChange={(event) => onChange(event.target.value)} />
      )}
    </label>
  );
}

function defaultValue(field: string) {
  if (field.startsWith("vista_")) return "OK";
  if (field === "overallStatus") return "Positivo";
  if (field === "periodicita") return "12 mesi";
  if (field === "tensione") return "220";
  if (field === "frequenza") return "50";
  if (field === "potenza_unit") return "W";
  if (field === "protezione") return "Trasformatore di isolamento";
  return "";
}

function labelFor(field: string) {
  const labels: Record<string, string> = {
    classe: "Classe",
    apType: "Parti applicate",
    potenza_unit: "Unita potenza",
    fusibili_conformita: "Fusibili conformita",
    overallStatus: "Esito",
    earthResPos: "Posizione resistenza terra",
  };
  return labels[field] || field.replaceAll("_", " ");
}

function DataBlock({ title, data, badges }: { title: string; data: Record<string, any>; badges?: Record<string, string> }) {
  return <div><h3 className="mb-2 text-sm font-semibold">{title}</h3><dl className="grid gap-2 text-sm">{Object.entries(data || {}).slice(0, 18).map(([key, value]) => <div key={key} className="border-b border-line pb-2"><dt className="text-xs uppercase text-slate-500">{key}</dt><dd className="break-words">{typeof value === "object" ? JSON.stringify(value).slice(0, 120) : String(value || "-")}</dd>{badges?.[key] && <span className="mt-1 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{badges[key]}</span>}</div>)}</dl></div>;
}
