from pathlib import Path
import re
from typing import Any

from app.services.ansur_template_detector import is_permanent_three_measure_template
from app.services.measurement_indexer import build_measurement_index


FIELD_MAP = {
    "manufacturer": ("produttore", "manufacturer", "marca"),
    "model": ("modello", "model"),
    "serial_number": ("matricola", "serial", "seriale", "s/n"),
    "inventory": ("inventario", "inventory", "asset"),
    "description": ("descrizione", "description", "device"),
    "location": ("reparto", "location", "ubicazione", "presidio"),
    "template_name": ("template", "procedura", "ansur"),
    "electrical_class": ("classe", "electrical class"),
    "applied_part_type": ("parte applicata", "applied part"),
    "date": ("data", "test date", "date"),
    "status": ("esito", "result", "status"),
    "instrument_serial": ("seriale strumento", "instrument serial", "analyzer serial"),
    "calibration_date": ("calibrazione", "calibration"),
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
        parts = [part.strip() for part in re.split(r";|\t|,", line, maxsplit=1)]
        if len(parts) < 2:
            match = re.match(r"\s*([^:=]+)\s*[:=]\s*(.+)", line)
            if not match:
                continue
            parts = [match.group(1).strip(), match.group(2).strip()]
        key = parts[0].lower()
        value = parts[1].strip()
        for canonical, aliases in FIELD_MAP.items():
            if any(alias in key for alias in aliases) and canonical not in result:
                result[canonical] = value
    return result


def _extract_measurements(lines: list[str]) -> list[dict[str, Any]]:
    measurements = []
    for line in lines:
        if not re.search(r"\b(pass|fail|ok|ko|ohm|ma|ua|µa|v|isolamento|earth|leakage)\b", line, re.IGNORECASE):
            continue
        parts = [part.strip() for part in re.split(r";|\t| {2,}", line) if part.strip()]
        if len(parts) < 2:
            continue
        measurements.append(
            {
                "name": parts[0],
                "value": parts[1],
                "unit": _unit(" ".join(parts)),
                "result": next((part for part in parts if part.upper() in {"PASS", "FAIL", "OK", "KO"}), ""),
                "condition": "",
                "parameter": "",
                "raw": line[:1000],
            }
        )
    return measurements


def _unit(text: str) -> str:
    match = re.search(r"\b(ohm|ma|ua|µa|v|mohm)\b", text, re.IGNORECASE)
    return match.group(1) if match else ""
