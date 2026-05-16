import re
from pathlib import Path

from app.services.ansur_parser import parse_ansur_mtr
from app.services.csv_parser import parse_esa615_csv
from app.services.esa615_legacy_adapter import parse_csv_legacy, parse_mtr_legacy
from app.services.measurement_indexer import build_measurement_index

FIELD_PATTERNS = {
    "matricola": [r"\bmatricola\b\s*[:=]\s*(.+)", r"\bserial\s*(?:number|no\.?)?\b\s*[:=]\s*(.+)", r"\bs/n\b\s*[:=]\s*(.+)"],
    "seriale": [r"\bseriale\b\s*[:=]\s*(.+)", r"\bserial\s*(?:number|no\.?)?\b\s*[:=]\s*(.+)", r"\bs/n\b\s*[:=]\s*(.+)"],
    "inventario": [r"\binventario\b\s*[:=]\s*(.+)", r"\basset\b\s*[:=]\s*(.+)"],
    "produttore": [r"\bproduttore\b\s*[:=]\s*(.+)", r"\bmanufacturer\b\s*[:=]\s*(.+)", r"\bmarca\b\s*[:=]\s*(.+)"],
    "modello": [r"\bmodello\b\s*[:=]\s*(.+)", r"\bmodel\b\s*[:=]\s*(.+)"],
    "descrizione": [r"\bdescrizione\b\s*[:=]\s*(.+)", r"\bdevice\b\s*[:=]\s*(.+)", r"\bequipment\b\s*[:=]\s*(.+)"],
    "reparto": [r"\breparto\b\s*[:=]\s*(.+)", r"\blocation\b\s*[:=]\s*(.+)"],
    "esito": [r"\besito\b\s*[:=]\s*(.+)", r"\bresult\b\s*[:=]\s*(.+)", r"\bpass/fail\b\s*[:=]\s*(.+)"],
}


def parse_mtr_file(path: str | Path) -> dict:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    if _looks_like_xml(content):
        try:
            parsed = _normalized_from_legacy_esa615(file_path, parse_mtr_legacy(file_path))
            try:
                parsed = _merge_xml_parses(parsed, parse_ansur_mtr(file_path))
            except Exception:
                pass
        except Exception:
            try:
                parsed = parse_ansur_mtr(file_path)
            except Exception:
                return _parse_text_mtr(file_path, content)
        return _legacy_from_normalized(parsed)
    if file_path.suffix.lower() == ".csv":
        try:
            parsed = _normalized_from_legacy_esa615(file_path, parse_csv_legacy(file_path))
            fallback = parse_esa615_csv(file_path)
            parsed = _merge_csv_parses(parsed, fallback)
        except Exception:
            parsed = parse_esa615_csv(file_path)
        return _legacy_from_normalized(parsed)
    return _parse_text_mtr(file_path, content)


def _parse_text_mtr(file_path: Path, content: str) -> dict:
    parsed = {"path": str(file_path), "nome_file": file_path.name, "raw_excerpt": content[:4000]}
    for field, patterns in FIELD_PATTERNS.items():
        parsed[field] = None
        for pattern in patterns:
            match = re.search(pattern, content, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                parsed[field] = _clean(match.group(1))
                break
    parsed["misure"] = _extract_measurements(content)
    normalized = _normalized_from_legacy(file_path, parsed)
    parsed["normalized"] = normalized
    parsed["measurement_index"] = build_measurement_index(normalized["measurements"])
    return parsed


def scan_mtr_folder(folder: str | Path) -> list[dict]:
    folder_path = Path(folder)
    if not folder_path.exists() or not folder_path.is_dir():
        raise FileNotFoundError(f"Cartella MTR non trovata: {folder_path}")
    paths = sorted({path.resolve() for path in [*folder_path.glob("*.MTR"), *folder_path.glob("*.mtr"), *folder_path.glob("*.csv"), *folder_path.glob("*.CSV")]})
    return [parse_mtr_file(path) for path in paths]


def _clean(value: str) -> str:
    return re.split(r"[\r\n;|]", value, maxsplit=1)[0].strip(" \t:-=")[:255] or ""


def _extract_measurements(content: str) -> list[dict[str, str]]:
    measurements = []
    for line in content.splitlines():
        if re.search(r"\b(pass|fail|ok|ko|ohm|ma|ua|v)\b", line, re.IGNORECASE):
            parts = re.split(r"\s{2,}|\t|;", line.strip())
            if len(parts) >= 2:
                measurements.append({"nome": parts[0][:120], "valore": parts[1][:120], "raw": line[:300]})
    return measurements[:100]


def _looks_like_xml(content: str) -> bool:
    stripped = content.lstrip("\ufeff\r\n\t ")
    return stripped.startswith("<?xml") or stripped.startswith("<")


def _legacy_from_normalized(normalized: dict) -> dict:
    dut = normalized.get("dut") or {}
    ansur = normalized.get("ansur") or {}
    test = normalized.get("test") or {}
    file_path = Path(normalized.get("source_path") or "")
    return {
        "path": str(file_path),
        "nome_file": file_path.name,
        "matricola": dut.get("serial_number"),
        "seriale": dut.get("serial_number"),
        "inventario": dut.get("inventory"),
        "produttore": dut.get("manufacturer"),
        "modello": dut.get("model"),
        "descrizione": dut.get("description"),
        "reparto": dut.get("department"),
        "stanza": dut.get("location"),
        "esito": test.get("status"),
        "template_ansur": ansur.get("template_name"),
        "is_permanent_three_measure_template": ansur.get("is_permanent_three_measure_template", False),
        "misure": [{"nome": item.get("name"), "valore": item.get("value"), "unita": item.get("unit"), "esito": item.get("result"), "raw": item.get("raw", "")} for item in normalized.get("measurements", [])],
        "normalized": normalized,
        "measurement_index": normalized.get("measurement_index") or build_measurement_index(normalized.get("measurements") or []),
        "raw_excerpt": "",
    }


def _normalized_from_legacy(file_path: Path, parsed: dict) -> dict:
    measurements = [
        {"name": item.get("nome"), "value": item.get("valore"), "unit": "", "result": "", "raw": item.get("raw", "")}
        for item in parsed.get("misure", [])
    ]
    return {
        "source_type": file_path.suffix.lower().lstrip(".") or "mtr",
        "source_path": str(file_path),
        "dut": {
            "manufacturer": parsed.get("produttore"),
            "model": parsed.get("modello"),
            "serial_number": parsed.get("matricola") or parsed.get("seriale"),
            "inventory": parsed.get("inventario"),
            "description": parsed.get("descrizione"),
            "location": parsed.get("reparto"),
        },
        "ansur": {"template_name": None, "electrical_class": None, "applied_part_type": None, "is_permanent_three_measure_template": False},
        "test": {"date": None, "status": parsed.get("esito")},
        "instrument": {"type": "ESA615", "manufacturer": "Fluke Biomedical", "serial_number": None, "calibration_date": None},
        "measurements": measurements,
    }


def _normalized_from_legacy_esa615(file_path: Path, legacy: dict) -> dict:
    measurements = [
        {
            "name": item.get("description"),
            "description": item.get("description"),
            "value": item.get("value"),
            "unit": item.get("unit"),
            "result": item.get("status"),
            "parameter": (item.get("parentType") or {}).get("param", ""),
            "test_element": (item.get("parentType") or {}).get("type", ""),
            "parentType": item.get("parentType") or {},
            "raw": "",
        }
        for item in legacy.get("measurements", [])
    ]
    return {
        "source_type": file_path.suffix.lower().lstrip(".") or "mtr",
        "source_path": str(file_path),
        "source_file": file_path.name,
        "legacy": legacy,
        "dut": {
            "manufacturer": legacy.get("manufacturer"),
            "model": legacy.get("model"),
            "serial_number": legacy.get("serialNumber"),
            "inventory": legacy.get("equipmentNumber"),
            "description": legacy.get("tipologia") or legacy.get("other"),
            "location": legacy.get("location"),
        },
        "ansur": {
            "template_name": legacy.get("templateName"),
            "electrical_class": legacy.get("classification"),
            "applied_part_type": legacy.get("apType"),
            "is_permanent_three_measure_template": bool(legacy.get("isPermanentThreeMeasure")),
        },
        "test": {"date": legacy.get("testDate"), "status": legacy.get("overallStatus")},
        "instrument": legacy.get("instrument") or {"type": "ESA615", "manufacturer": "Fluke Biomedical", "serial_number": None, "calibration_date": None},
        "measurements": measurements,
        "measurement_index": build_measurement_index(measurements),
    }


def _merge_csv_parses(primary: dict, fallback: dict) -> dict:
    merged = dict(primary)
    for section in ("dut", "ansur", "test", "instrument"):
        primary_section = dict(primary.get(section) or {})
        fallback_section = fallback.get(section) or {}
        for key, value in fallback_section.items():
            if not primary_section.get(key):
                primary_section[key] = value
        merged[section] = primary_section
    if not merged.get("measurements") and fallback.get("measurements"):
        merged["measurements"] = fallback["measurements"]
        merged["measurement_index"] = fallback.get("measurement_index") or build_measurement_index(fallback["measurements"])
    return merged


def _merge_xml_parses(primary: dict, fallback: dict) -> dict:
    merged = dict(primary)
    for section in ("dut", "ansur", "test", "instrument"):
        primary_section = dict(primary.get(section) or {})
        fallback_section = fallback.get(section) or {}
        for key, value in fallback_section.items():
            if not primary_section.get(key):
                primary_section[key] = value
        merged[section] = primary_section
    if not merged.get("measurements") and fallback.get("measurements"):
        merged["measurements"] = fallback["measurements"]
        merged["measurement_index"] = fallback.get("measurement_index") or build_measurement_index(fallback["measurements"])
    return merged
