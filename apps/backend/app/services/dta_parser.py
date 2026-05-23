from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any

from app.services.ansur_template_detector import is_permanent_three_measure_template
from app.services.measurement_indexer import build_measurement_index


TEST_NAMES = {
    "PERE": "Protective Earth Resistance",
    "INSM-PE": "Insulation Resistance PE",
    "INSM-AP": "Insulation Resistance Applied Part",
    "INS-APNE": "Insulation Resistance Applied Part to Mains",
    "VOLTSLN": "Line Neutral Voltage",
    "VOLTSNE": "Neutral Earth Voltage",
    "VOLTSLE": "Line Earth Voltage",
    "EQUIP": "Equipment Current",
    "DMAP-AC-PNECNC": "Applied Part Leakage Current Normal Polarity",
    "DMAP-AC-PRECNC": "Applied Part Leakage Current Reverse Polarity",
    "DIRL-ACDC-PNEONC": "Direct Applied Part Leakage Current Normal Polarity",
    "DIRL-ACDC-PREONC": "Direct Applied Part Leakage Current Reverse Polarity",
}

VALUE_UNITS = {
    "O": "ohm",
    "M": "MOhm",
    "V": "V",
    "A": "A",
    "U": "uA",
}


def parse_esa615_dta(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    header = _parse_header(content)
    measurements = _parse_measurements(content)
    test_status = _overall_status(measurements)
    normalized = {
        "source_type": "dta",
        "source_path": str(file_path),
        "source_file": file_path.name,
        "dut": {
            "manufacturer": _empty_to_none(header.get("DUTMANF")),
            "model": _empty_to_none(header.get("DUTMODEL")),
            "serial_number": _empty_to_none(header.get("DUTSN")),
            "inventory": _empty_to_none(header.get("DUTEQUIPNUM")),
            "description": _empty_to_none(header.get("OTHER")),
            "location": _empty_to_none(header.get("DUTLOC")),
        },
        "ansur": {
            "template_name": _empty_to_none(header.get("MASTERFILE") or header.get("NAME")),
            "electrical_class": _empty_to_none(header.get("CLASSIFICATION")),
            "applied_part_type": _first_csv_value(header.get("APTYPE")),
            "is_permanent_three_measure_template": False,
        },
        "test": {
            "date": _test_datetime(header),
            "status": test_status,
            "duration_seconds": _empty_to_none(header.get("TESTDURATION")),
            "standard": _empty_to_none(header.get("STANDARD")),
        },
        "instrument": {
            "type": "ESA615",
            "manufacturer": "Fluke Biomedical",
            "serial_number": _empty_to_none(header.get("ESA615SN")),
            "version": _empty_to_none(header.get("ESA615UIFW")),
            "calibration_date": _parse_calibration_date(header.get("ESA615CALDATE")),
            "calibration_tech": _empty_to_none(header.get("ESA615CALTECH")),
        },
        "measurements": measurements,
        "legacy": {"header": header},
        "unrecognized": [],
    }
    normalized["ansur"]["is_permanent_three_measure_template"] = is_permanent_three_measure_template(
        normalized["ansur"].get("template_name") or "",
        measurements,
    )
    normalized["measurement_index"] = build_measurement_index(measurements)
    return normalized


def _parse_header(content: str) -> dict[str, str]:
    match = re.search(r"<HEADER>\s*(.*?)\s*<\\HEADER>", content, flags=re.IGNORECASE | re.DOTALL)
    source = match.group(1) if match else content
    return {key.strip().upper(): value.strip() for key, value in re.findall(r"^([A-Z0-9]+)=(.*)$", source, flags=re.MULTILINE)}


def _parse_measurements(content: str) -> list[dict[str, Any]]:
    result = []
    pattern = re.compile(r"<(TESTAP|TEST)=([^>]+)>\s*(.*?)\s*<\\\1>", flags=re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(content):
        kind = match.group(1).upper()
        code = match.group(2).strip().upper()
        raw_row = " ".join(match.group(3).strip().splitlines()).strip()
        parts = [part.strip() for part in raw_row.split(",")]
        value_token = _value_token(parts)
        if not value_token:
            continue
        prefix, value = value_token[0].upper(), value_token[1:]
        status = _status(parts[-1] if parts else "")
        measurement = {
            "name": TEST_NAMES.get(code, code),
            "description": TEST_NAMES.get(code, code),
            "value": value,
            "unit": VALUE_UNITS.get(prefix, ""),
            "result": status,
            "parameter": code,
            "test_element": kind,
            "raw": raw_row,
            "parentType": {"type": kind, "param": code},
        }
        if kind == "TESTAP" and parts:
            measurement["applied_part"] = parts[0]
        high_limit = _limit(parts, kind)
        if high_limit:
            measurement["high_limit"] = high_limit
        result.append(measurement)
    return result


def _value_token(parts: list[str]) -> str:
    for part in parts:
        token = part.strip()
        if re.fullmatch(r"[OMVAU]-?\d+(?:[.,]\d+)?", token, flags=re.IGNORECASE):
            return token.replace(",", ".")
    return ""


def _limit(parts: list[str], kind: str) -> str:
    candidates = parts[1:3] if kind == "TESTAP" else parts[:2]
    for part in candidates:
        if part and part != "-" and re.fullmatch(r"-?\d+(?:[.,]\d+)?", part):
            return part.replace(",", ".")
    return ""


def _status(value: str) -> str:
    token = value.strip().upper()
    if token == "P":
        return "PASS"
    if token in {"F", "FAIL", "FAILED"}:
        return "FAIL"
    return token if token not in {"", "-"} else ""


def _overall_status(measurements: list[dict[str, Any]]) -> str | None:
    statuses = {str(item.get("result") or "").upper() for item in measurements}
    if "FAIL" in statuses:
        return "FAIL"
    if "PASS" in statuses:
        return "PASS"
    return None


def _test_datetime(header: dict[str, str]) -> str | None:
    date_value = header.get("DATEOFTEST")
    time_value = header.get("TIMEOFTEST")
    if not date_value:
        return None
    raw = f"{date_value} {time_value or '00:00'}"
    for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).isoformat(timespec="minutes")
        except ValueError:
            continue
    return date_value


def _parse_calibration_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(r"M(\d{1,2})D(\d{1,2})Y(\d{4})", value.strip(), flags=re.IGNORECASE)
    if not match:
        return value.strip()
    month, day, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _first_csv_value(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(",", 1)[0].strip()
    return first or None


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
