export function formatItalianDate(value: unknown) {
  if (!value) return "-";
  const text = String(value).trim();
  if (!text) return "-";
  const date = parseDate(text);
  return date ? date.toLocaleDateString("it-IT") : text;
}

export function formatItalianDateTime(value: unknown) {
  if (!value) return "-";
  const text = String(value).trim();
  if (!text) return "-";
  const date = parseDate(text);
  return date ? date.toLocaleString("it-IT") : text;
}

function parseDate(text: string) {
  const italian = text.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (italian) return new Date(Number(italian[3]), Number(italian[2]) - 1, Number(italian[1]));
  const isoDate = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (isoDate) return new Date(Number(isoDate[1]), Number(isoDate[2]) - 1, Number(isoDate[3]));
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}
