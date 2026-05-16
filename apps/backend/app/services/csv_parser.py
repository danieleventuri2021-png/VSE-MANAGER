from pathlib import Path
import csv
import re
from typing import Any

from app.services.ansur_template_detector import is_permanent_three_measure_template
from app.services.measurement_indexer import build_measurement_index


FIELD_MAP = {
    "manufacturer": ("produttore", "manufacturer", "marca"),
    "model": ("modello", "model"),
    "serial_number": ("matricola", "serial number", "seriale", "s/n"),
    "inventory": ("inventario", "inventory", "asset", "equipment number"),
    "description": ("descrizione", "description", "device", "other"),
    "location": ("reparto", "location", "ubicazione", "presidio"),
    "template_name": ("template name", "template", "procedura", "ansur"),
    "electrical_class": ("classification", "classe", "electrical class"),
    "applied_part_type": ("ap type", "applied part type", "parte applicata", "applied part"),
    "date": ("date & time", "test date", "date", "data"),
    "status": ("esito", "result", "status"),
    "instrument_serial": ("seriale strumento", "instrument serial", "analyzer serial"),
    "calibration_date": ("calibration date", "calibrazione", "calibration"),
}


def parse_esa615_csv(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    fields = _extract_fields(lines)
    measurements = _extract_measurements(lines)
    template_name = fields.get("template_name")
    parsed = {
        "source_type": "csv",
        "source_path": str(file_path),
        "dut": {
            "manufacturer": fields.get("manufacturer"),
            "model": fields.get("model"),
            "serial_number": fields.get("serial_number"),
            "inventory": fields.get("inventory"),
            "description": fields.get("description"),
            "location": fields.get("location"),
        },
        "ansur": {
            "template_name": template_name,
            "electrical_class": fields.get("electrical_class"),
            "applied_part_type": fields.get("applied_part_type"),
            "is_permanent_three_measure_template": is_permanent_three_measure_template(template_name or "", measurements),
        },
        "test": {"date": fields.get("date"), "status": (fields.get("status") or "").upper()},
        "instrument": {
            "type": "ESA615",
            "manufacturer": "Fluke Biomedical",
            "serial_number": fields.get("instrument_serial"),
            "calibration_date": fields.get("calibration_date"),
        },
        "measurements": measurements,
        "unrecognized": [],
    }
    parsed["measurement_index"] = build_measurement_index(measurements)
    return parsed


def _extract_fields(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        cells = _split_cells(line)
        lower_cells = [_normalize_key(cell) for cell in cells]
        for index, raw_cell in enumerate(cells):
            key, inline_value = _split_key_value(raw_cell)
            if not key:
                continue
            canonical = _canonical_field(key)
            if not canonical:
                continue
            value = inline_value or _next_value(cells, index + 1)
            if not value:
                continue
            canonical = _resolve_serial_context(canonical, lower_cells, result)
            if canonical not in result:
                result[canonical] = value
    return result


def _extract_measurements(lines: list[str]) -> list[dict[str, Any]]:
    measurements = []
    for line in lines:
        if not re.search(r"\b(pass|fail|ok|ko|ohm|ma|ua|µa|v|a|current|isolamento|earth|leakage)\b", line, re.IGNORECASE):
            continue
        parts = [part.strip() for part in _split_cells(line) if part.strip()]
        if len(parts) < 2:
            continue
        if _is_header_or_field_row(parts):
            continue
        result = _result(parts)
        value = _measurement_value(parts)
        measurements.append(
            {
                "name": parts[0],
                "value": value,
                "unit": _unit(" ".join(parts)),
                "result": result,
                "condition": "",
                "parameter": "",
                "raw": line[:1000],
            }
        )
    return measurements


def _split_cells(line: str) -> list[str]:
    delimiter = ";" if line.count(";") >= line.count(",") and ";" in line else ","
    if "\t" in line and line.count("\t") > line.count(delimiter):
        delimiter = "\t"
    try:
        return [cell.strip() for cell in next(csv.reader([line], delimiter=delimiter))]
    except csv.Error:
        return [cell.strip() for cell in re.split(r";|\t|,", line)]


def _split_key_value(cell: str) -> tuple[str, str]:
    match = re.match(r"\s*([^:=]+?)\s*[:=]\s*(.*)\s*$", cell)
    if match:
        return _normalize_key(match.group(1)), match.group(2).strip()
    return _normalize_key(cell), ""


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip(":=").lower())


def _canonical_field(key: str) -> str | None:
    for canonical, aliases in FIELD_MAP.items():
        if any(alias == key or alias in key for alias in aliases):
            return canonical
    return None


def _next_value(cells: list[str], start: int) -> str:
    for cell in cells[start:]:
        value = cell.strip()
        if value:
            return value[:255]
    return ""


def _resolve_serial_context(canonical: str, row_keys: list[str], result: dict[str, str]) -> str:
    if canonical != "serial_number":
        return canonical
    if any("firmware version" in key for key in row_keys) or "serial_number" in result:
        return "instrument_serial"
    return canonical


def _is_header_or_field_row(parts: list[str]) -> bool:
    first = _normalize_key(parts[0])
    if first in {"test name", "test setup", "esa615 test results"}:
        return True
    return bool(_canonical_field(first))


def _measurement_value(parts: list[str]) -> str:
    for part in parts[1:]:
        if re.search(r"\d", part):
            return part
    return parts[1]


def _result(parts: list[str]) -> str:
    status_map = {"P": "PASS", "F": "FAIL", "PASS": "PASS", "FAIL": "FAIL", "OK": "OK", "KO": "KO"}
    for part in reversed(parts):
        status = status_map.get(part.strip().upper())
        if status:
            return status
    return ""


def _unit(text: str) -> str:
    match = re.search(r"\b(ohm|ma|ua|µa|v|a|mohm)\b", text, re.IGNORECASE)
    return match.group(1) if match else ""
