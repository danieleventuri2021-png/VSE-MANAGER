export function badgeClass(status: string) {
  const normalized = status.replaceAll("_", "-");
  if (normalized.includes("certo")) return "bg-emerald-100 text-emerald-800 border-emerald-200";
  if (normalized.includes("controllare")) return "bg-amber-100 text-amber-800 border-amber-200";
  if (normalized.includes("anomalia") || normalized.includes("mancante") || normalized.includes("error")) return "bg-rose-100 text-rose-800 border-rose-200";
  if (normalized.includes("orfano")) return "bg-sky-100 text-sky-800 border-sky-200";
  return "bg-slate-100 text-slate-700 border-slate-200";
}
