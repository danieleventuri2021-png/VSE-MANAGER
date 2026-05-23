import { Fragment, useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, Check, ChevronDown, ChevronRight, GitCompare } from "lucide-react";
import { api, type Job } from "../api/client";
import { Badge } from "../components/Badge";
import { Panel } from "../components/Panel";
import { RefreshButton } from "../components/RefreshButton";

export function Matches({ jobs }: { jobs: Job[] }) {
  const [jobId, setJobId] = useState<number>(jobs[0]?.id ?? 0);
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [openRow, setOpenRow] = useState<number | null>(null);
  const [choices, setChoices] = useState<Record<string, "mtr_from_excel" | "excel_from_mtr">>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/api/jobs/${jobId}/matches`);
      setRows(data);
      setChoices({});
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    setRows([]);
    setOpenRow(null);
    load();
  }, [load]);

  return (
    <Panel title="Abbinamenti" action={<RefreshButton loading={loading} onClick={load} />}>
      <div className="mb-3">
        <select className="h-10 rounded-md border border-line px-3 text-sm" value={jobId} onChange={(event) => setJobId(Number(event.target.value))}>
          <option value={0}>Seleziona lavoro</option>
          {jobs.map((job) => <option key={job.id} value={job.id}>{job.id} - {job.titolo}</option>)}
        </select>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Riga</th><th>Matricola</th><th>Produttore</th><th>Modello</th><th>MTR/CSV/DTA</th><th>Stato</th><th>Score</th></tr></thead>
          <tbody>
            {rows.map((row, index) => {
              const expandable = row.status !== "certo" || row.differences?.fields?.length > 0;
              const opened = openRow === index;
              return (
                <Fragment key={index}>
                  <tr className={`border-t border-line ${expandable ? "cursor-pointer bg-amber-50 hover:bg-amber-100" : ""}`} onClick={() => expandable && setOpenRow(opened ? null : index)}>
                    <td className="py-2">
                      <span className="inline-flex items-center gap-1">
                        {expandable ? opened ? <ChevronDown size={15} /> : <ChevronRight size={15} /> : <span className="w-[15px]" />}
                        {row.equipment?.row_index ?? "-"}
                      </span>
                    </td>
                    <td>{row.equipment?.matricola || row.equipment?.seriale || row.mtr?.matricola || row.mtr?.seriale || "-"}</td>
                    <td>{row.equipment?.produttore || row.mtr?.produttore || "-"}</td>
                    <td>{row.equipment?.modello || row.mtr?.modello || "-"}</td>
                    <td>{row.mtr?.nome_file || "-"}</td>
                    <td><Badge status={row.status}>{row.status}</Badge></td>
                    <td>{row.score?.toFixed?.(1) ?? "-"}</td>
                  </tr>
                  {opened && <tr className="border-t border-line bg-slate-50"><td colSpan={7}><MatchDetail row={row} rowIndex={index} choices={choices} setChoices={setChoices} onConfirm={confirmChoices} saving={saving} /></td></tr>}
                </Fragment>
              );
            })}
          </tbody>
        </table>
        {!loading && jobId > 0 && rows.length === 0 && <p className="border-t border-line py-4 text-sm text-slate-500">Nessun abbinamento disponibile. Importa Excel/MTR/CSV/DTA e avvia Analizza per questo lavoro.</p>}
      </div>
    </Panel>
  );

  async function confirmChoices(row: any, rowIndex: number) {
    const fields = Object.entries(choices)
      .filter(([key]) => key.startsWith(`${rowIndex}:`))
      .map(([key, direction]) => ({ field: key.split(":")[1], direction }));
    if (!jobId || !row.equipment?.id || !row.mtr?.id || fields.length === 0 || saving) return;
    setSaving(true);
    try {
      await api.post(`/api/jobs/${jobId}/matches/resolve`, { equipment_id: row.equipment.id, file_mtr_id: row.mtr.id, fields });
      await load();
      setOpenRow(rowIndex);
    } finally {
      setSaving(false);
    }
  }
}

function MatchDetail({
  row,
  rowIndex,
  choices,
  setChoices,
  onConfirm,
  saving,
}: {
  row: any;
  rowIndex: number;
  choices: Record<string, "mtr_from_excel" | "excel_from_mtr">;
  setChoices: (choices: Record<string, "mtr_from_excel" | "excel_from_mtr">) => void;
  onConfirm: (row: any, rowIndex: number) => void;
  saving: boolean;
}) {
  const fields = row.differences?.fields || [];
  const selected = fields.filter((field: any) => choices[choiceKey(rowIndex, field.field)]).length;
  return (
    <div className="grid gap-3 p-3 text-sm">
      <div className="flex items-center gap-2 text-slate-700">
        <GitCompare size={16} />
        <span className="font-medium">{row.reason || "Dettaglio abbinamento"}</span>
      </div>
      {row.status === "mancante" && <Notice text="Questa riga Excel non ha un file MTR/CSV/DTA associato con sufficiente confidenza." />}
      {row.status === "mtr_orfano" && <Notice text="Questo file MTR/CSV/DTA non è stato collegato ad alcuna riga Excel." />}
      {row.registry_match && (
        <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sky-900">
          <div className="font-medium">Possibile apparecchiatura gia presente in archivio</div>
          <div className="mt-1 text-xs">
            {row.registry_match.match_reason} - {row.registry_match.cliente_nome} / {row.registry_match.tipologia || "-"} / {row.registry_match.produttore || "-"} {row.registry_match.modello || "-"} / Matricola {row.registry_match.matricola || "-"} / INVGEST {row.registry_match.inventario_gestionale || "-"}
          </div>
        </div>
      )}
      {fields.length > 0 ? (
        <div className="overflow-x-auto rounded-md border border-line bg-white">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100 uppercase text-slate-500"><tr><th className="p-2">Campo</th><th>Excel</th><th>MTR/CSV/DTA</th><th>Allinea</th></tr></thead>
            <tbody>
              {fields.map((field: any) => {
                const key = choiceKey(rowIndex, field.field);
                const choice = choices[key];
                return (
                <tr className="border-t border-line" key={field.field}>
                  <td className="p-2 font-medium">{field.field}</td>
                  <td className="pr-2">{field.excel || "-"}</td>
                  <td className="pr-2">{field.mtr || "-"}</td>
                  <td className="p-2">
                    <div className="flex flex-wrap gap-2">
                      <button
                        className={`inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs ${choice === "mtr_from_excel" ? "border-action bg-blue-50 text-action" : "border-line bg-white"}`}
                        title="Aggiorna MTR/CSV/DTA con il valore Excel"
                        onClick={() => setChoices({ ...choices, [key]: "mtr_from_excel" })}
                      >
                        Excel <ArrowRight size={14} /> MTR/CSV/DTA
                      </button>
                      <button
                        className={`inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs ${choice === "excel_from_mtr" ? "border-action bg-blue-50 text-action" : "border-line bg-white"}`}
                        title="Aggiorna Excel/database con il valore MTR/CSV/DTA"
                        onClick={() => setChoices({ ...choices, [key]: "excel_from_mtr" })}
                      >
                        Excel <ArrowLeft size={14} /> MTR/CSV/DTA
                      </button>
                    </div>
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-2 rounded-md border border-line bg-white p-3 sm:grid-cols-2">
          <DataBlock title="Excel" data={row.equipment} />
          <DataBlock title="MTR/CSV/DTA" data={row.mtr} />
        </div>
      )}
      {fields.length > 0 && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-white p-3">
          <span className="text-xs text-slate-500">{selected} campi selezionati per l'allineamento</span>
          <button className="inline-flex h-9 items-center gap-2 rounded-md bg-action px-3 text-sm text-white disabled:cursor-not-allowed disabled:opacity-60" disabled={selected === 0 || saving} onClick={() => onConfirm(row, rowIndex)}>
            <Check size={16} /> {saving ? "Conferma..." : "Conferma allineamento"}
          </button>
        </div>
      )}
    </div>
  );
}

function choiceKey(rowIndex: number, field: string) {
  return `${rowIndex}:${field}`;
}

function Notice({ text }: { text: string }) {
  return <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-amber-800"><AlertTriangle size={16} /> {text}</div>;
}

function DataBlock({ title, data }: { title: string; data: any }) {
  const fields = ["matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto", "stanza"];
  return (
    <div>
      <div className="mb-2 font-medium text-slate-700">{title}</div>
      <dl className="grid gap-1">
        {fields.map((field) => <div className="grid grid-cols-3 gap-2" key={field}><dt className="text-slate-500">{field}</dt><dd className="col-span-2 break-words">{data?.[field] || "-"}</dd></div>)}
      </dl>
    </div>
  );
}
