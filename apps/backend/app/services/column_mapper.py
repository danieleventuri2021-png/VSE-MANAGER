import re
import unicodedata
from collections.abc import Iterable

ALIASES = {
    "matricola": ["matricola", "seriale", "s/n", "sn", "numero serie", "n serie", "n. serie"],
    "seriale": ["seriale", "serial number", "serie", "s/n", "sn"],
    "inventario": ["inventario", "numero inventario", "cespite", "asset", "inv"],
    "produttore": ["produttore", "costruttore", "marca", "manufacturer"],
    "modello": ["modello", "model", "tipo", "type"],
    "descrizione": ["descrizione", "tipologia", "apparecchio", "dispositivo", "equipment", "nome apparecchio"],
    "reparto": ["reparto", "servizio", "area"],
    "stanza": ["stanza", "locale", "ambiente", "location", "ubicazione"],
    "esito": ["esito", "risultato", "conforme", "pass fail", "stato verifica"],
    "data_verifica": ["data verifica", "data", "verification date", "test date"],
}


def normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def map_columns(columns: Iterable[object]) -> dict[str, str]:
    normalized = {normalize_header(col): str(col) for col in columns}
    result: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        candidates = [normalize_header(canonical), *(normalize_header(alias) for alias in aliases)]
        for candidate in candidates:
            if candidate in normalized:
                result[canonical] = normalized[candidate]
                break
        if canonical not in result:
            for header_norm, original in normalized.items():
                if any(candidate and candidate in header_norm for candidate in candidates):
                    result[canonical] = original
                    break
    return result


def extract_row(row: dict, mapping: dict[str, str]) -> dict:
    return {key: clean_value(row.get(column)) for key, column in mapping.items()}


def clean_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text
