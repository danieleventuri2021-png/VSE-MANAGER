import { FileCheck, Save, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { applyJobDefaults, generateOnePdf, getReview, getReviewDetail, saveJobSettings, saveReview, saveSource, type Job } from "../api/client";
import { Badge } from "../components/Badge";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";

const genericFieldGroups = [
  { title: "Dati identificativi", fields: ["tipologia", "manufacturer", "model", "serial", "civab", "proprieta", "invGest", "invEnte", "presidio", "reparto", "stanza", "periodicita", "classe", "apType"] },
  { title: "Dati tecnici", fields: ["installazione", "mobilita", "tensione", "frequenza", "potenza", "potenza_unit", "protezione", "fusibili_conformita", "dati_targa_fusibili", "valore_nominale", "protezione_altro"] },
  { title: "Esame a vista", fields: ["vista_targa", "vista_telaio", "vista_parti_mov", "vista_cavo", "vista_passacavo", "vista_spie", "vista_parti_appl", "vista_doc"] },
  { title: "Tecnico, misure ed esito", fields: ["tecnico", "firma_path", "earthResPos", "funz_accensione", "funz_codice_prot", "funz_normativa", "funz_prova_part", "overallStatus", "note"] },
];

const consipFieldGroups = [
  { title: "Sezione anagrafica", fields: ["invGest", "tipologia", "manufacturer", "model", "serial", "proprieta", "presidio", "reparto", "stanza"] },
  { title: "Dati tecnici", fields: ["tensione", "potenza", "potenza_unit", "classe", "apType", "periodicita", "installazione_consip"] },
  { title: "Condizioni di prova", fields: ["consip_valori_prima_misura", "consip_norma_riferimento", "consip_metodo_misura", "consip_boot_calibrazione", "consip_cavi_terra_supplementari", "consip_classe_alimentazione_sicurezza", "consip_trasformatore_isolamento", "consip_connessione_nodo_locale"] },
  { title: "Controllo visivo iniziale", fields: ["vista_funzionamento", "vista_telaio", "vista_parti_mov", "vista_ruote", "vista_spine", "vista_cavo", "vista_passacavo", "vista_targa", "vista_spie", "vista_tubazioni", "vista_doc"] },
  { title: "Esito e firma", fields: ["funz_accensione", "consip_valutazione_finale", "consip_provvedimenti_note", "tecnico", "firma_path", "consip_copia_firma_responsabile"] },
];

const allEditableFields = Array.from(new Set([...genericFieldGroups, ...consipFieldGroups].flatMap((group) => group.fields)));

const options: Record<string, { value: string; label: string }[]> = {
  periodicita: [{ value: "12 mesi", label: "12 mesi" }, { value: "24 mesi", label: "24 mesi" }],
  classe: [{ value: "I", label: "I" }, { value: "II", label: "II" }, { value: "AI", label: "AI" }],
  apType: [{ value: "B", label: "B" }, { value: "BF", label: "BF" }, { value: "CF", label: "CF" }],
  installazione: [{ value: "Permanente", label: "Permanente" }, { value: "Non permanente", label: "Non permanente" }],
  installazione_consip: [{ value: "fissa", label: "fissa" }, { value: "cavo separabile", label: "cavo separabile" }, { value: "cavo non separabile", label: "cavo non separabile" }],
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
  vista_funzionamento: consipVisualOptions(),
  vista_ruote: consipVisualOptions(),
  vista_spine: consipVisualOptions(),
  vista_tubazioni: consipVisualOptions(),
  vista_doc: visualOptions(),
  funz_accensione: [{ value: "", label: "-" }, ...visualOptions()],
  funz_prova_part: [{ value: "", label: "-" }, ...visualOptions()],
  overallStatus: [{ value: "Positivo", label: "Positivo" }, { value: "Negativo", label: "Negativo" }, { value: "Da revisionare", label: "Apparecchiatura da revisionare / necessita manutenzione" }],
  consip_valori_prima_misura: yesNoOptions(),
  consip_norma_riferimento: [{ value: "62-5", label: "62-5" }, { value: "62-148", label: "62-148" }],
  consip_metodo_misura: [{ value: "Differenziale", label: "Differenziale" }, { value: "Alternativo", label: "Alternativo" }, { value: "Diretto", label: "Diretto" }],
  consip_boot_calibrazione: yesNoOptions(),
  consip_cavi_terra_supplementari: yesNoOptions(),
  consip_trasformatore_isolamento: yesNoOptions(),
  consip_connessione_nodo_locale: yesNoOptions(),
  consip_valutazione_finale: [
    { value: "CONFORME", label: "CONFORME" },
    { value: "NON CONFORMITA FORMALE", label: "NON CONFORMITA' FORMALE" },
    { value: "NON CONFORMITA SOSTANZIALE", label: "NON CONFORMITA' SOSTANZIALE" },
    { value: "NON CONFORMITA GRAVE", label: "NON CONFORMITA' GRAVE" },
  ],
  consip_copia_firma_responsabile: yesNoOptions(),
};

function visualOptions() {
  return [{ value: "OK", label: "OK" }, { value: "KO", label: "NO OK" }, { value: "NA", label: "NA" }];
}

function consipVisualOptions() {
  return [{ value: "OK", label: "ok" }, { value: "KO", label: "non ok" }, { value: "NV", label: "non verificabile" }, { value: "NA", label: "non applicabile" }];
}

function yesNoOptions() {
  return [{ value: "SI", label: "SI" }, { value: "NO", label: "NO" }];
}

export function ReviewMtr({ jobs, mode = "full" }: { jobs: Job[]; mode?: "full" | "simple" }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [items, setItems] = useState<any[]>([]);
  const [selected, setSelected] = useState<number>(0);
  const [detail, setDetail] = useState<any>(null);
  const [fields, setFields] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [loadingList, setLoadingList] = useState(false);
  const selectedJob = jobs.find((job) => job.id === jobId);
  const isConsip = (selectedJob?.template_pdf || "").toLowerCase() === "consip";
  const activeGroups = isConsip ? consipFieldGroups : genericFieldGroups;

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
    setFields(Object.fromEntries(allEditableFields.map((field) => [field, data.final?.[field] ?? defaultValue(field)])));
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
    setMessage("Valori comuni applicati agli MTR/CSV/DTA non bloccati");
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
      <Panel title="MTR/CSV/DTA del lavoro" action={<RefreshButton loading={loadingList} onClick={loadList} />}>
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
            <Panel title={`Revisione MTR/CSV/DTA - campi modulo ${isConsip ? "CONSIP" : "VSS.GEN"}`} action={<div className="flex flex-wrap gap-2"><button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={saveAsJobDefaults}>Salva default lavoro</button><button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={applyDefaults}><ShieldCheck size={16} /> Applica a tutti</button><button className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-sm text-white" onClick={save}><Save size={16} /> Applica solo a questo MTR/CSV/DTA</button></div>}>
              <div className="grid gap-5">
                {activeGroups.map((group) => (
                  <section key={group.title}>
                    <h3 className="mb-2 text-sm font-semibold text-ink">{group.title}</h3>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {group.fields.map((field) => <FieldControl key={field} field={field} value={fields[field] ?? defaultValue(field)} isConsip={isConsip} onChange={(value) => setFields({ ...fields, [field]: value })} />)}
                    </div>
                  </section>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {mode === "full" && <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={() => saveSource(selected, { fields })}>Salva nel sorgente MTR/CSV/DTA</button>}
                <button className="inline-flex h-9 items-center gap-2 rounded-md border border-line px-3 text-sm" onClick={() => generateOnePdf(jobId, selected)}><FileCheck size={16} /> Genera PDF singolo</button>
              </div>
            </Panel>
            <Panel title={mode === "simple" ? "Dati sorgente e finali" : "Dati sorgente, Excel e finali"}>
              <div className={`grid gap-4 ${mode === "simple" ? "lg:grid-cols-2" : "lg:grid-cols-3"}`}>
                <DataBlock title="MTR/CSV/DTA / Ansur" data={detail.source} />
                {mode === "full" && <DataBlock title="Excel associato" data={detail.excel} />}
                <DataBlock title="Finale PDF" data={detail.final} badges={detail.badges} />
              </div>
            </Panel>
          </>
        )}
      </div>
    </div>
  );
}

function FieldControl({ field, value, isConsip, onChange }: { field: string; value: string; isConsip: boolean; onChange: (value: string) => void }) {
  const fieldOptions = optionsFor(field, isConsip);
  return (
    <label className="grid gap-1 text-xs font-medium uppercase text-slate-500">
      {labelFor(field)}
      {fieldOptions ? (
        <select className="h-10 rounded-md border border-line px-3 text-sm normal-case text-ink" value={value} onChange={(event) => onChange(event.target.value)}>
          {fieldOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      ) : (
        field === "consip_provvedimenti_note" ? (
          <textarea className="min-h-24 rounded-md border border-line px-3 py-2 text-sm normal-case text-ink" value={value} onChange={(event) => onChange(event.target.value)} />
        ) : (
          <input className="h-10 rounded-md border border-line px-3 text-sm normal-case text-ink" value={value} onChange={(event) => onChange(event.target.value)} />
        )
      )}
    </label>
  );
}

function optionsFor(field: string, isConsip: boolean) {
  if (isConsip && field.startsWith("vista_")) return consipVisualOptions();
  return options[field];
}

function defaultValue(field: string) {
  if (field.startsWith("vista_")) return "OK";
  if (field === "overallStatus") return "Positivo";
  if (field === "periodicita") return "12 mesi";
  if (field === "tensione") return "220";
  if (field === "frequenza") return "50";
  if (field === "potenza_unit") return "W";
  if (field === "protezione") return "Trasformatore di isolamento";
  if (field === "installazione_consip") return "cavo separabile";
  if (field === "consip_valori_prima_misura") return "SI";
  if (field === "consip_norma_riferimento") return "62-148";
  if (field === "consip_metodo_misura") return "Diretto";
  if (field === "consip_boot_calibrazione") return "NO";
  if (field === "consip_cavi_terra_supplementari") return "NO";
  if (field === "consip_trasformatore_isolamento") return "NO";
  if (field === "consip_connessione_nodo_locale") return "NO";
  if (field === "consip_valutazione_finale") return "CONFORME";
  if (field === "consip_copia_firma_responsabile") return "NO";
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
    installazione_consip: "Tipo di installazione",
    consip_valori_prima_misura: "Valori di prima misura",
    consip_norma_riferimento: "Norma di riferimento",
    consip_metodo_misura: "Metodo di misura",
    consip_boot_calibrazione: "Fase boot / calibrazione motore",
    consip_cavi_terra_supplementari: "Cavi di terra supplementari",
    consip_classe_alimentazione_sicurezza: "Classe alimentazione sicurezza 64.8",
    consip_trasformatore_isolamento: "Trasformatore isolamento",
    consip_connessione_nodo_locale: "Connessione diretta nodo locale",
    consip_valutazione_finale: "Valutazione finale",
    consip_provvedimenti_note: "Provvedimenti / note",
    consip_copia_firma_responsabile: "Copia firma anche su responsabile verifiche",
  };
  return labels[field] || field.replaceAll("_", " ");
}

function DataBlock({ title, data, badges }: { title: string; data: Record<string, any>; badges?: Record<string, string> }) {
  return <div><h3 className="mb-2 text-sm font-semibold">{title}</h3><dl className="grid gap-2 text-sm">{Object.entries(data || {}).slice(0, 18).map(([key, value]) => <div key={key} className="border-b border-line pb-2"><dt className="text-xs uppercase text-slate-500">{key}</dt><dd className="break-words">{typeof value === "object" ? JSON.stringify(value).slice(0, 120) : String(value || "-")}</dd>{badges?.[key] && <span className="mt-1 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{badges[key]}</span>}</div>)}</dl></div>;
}
