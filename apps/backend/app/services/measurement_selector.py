import re
from typing import Any

from app.services.measurement_indexer import measurement_text, normalize_text


PE_KEYWORDS = ("protective earth", "terra", "earth resistance", "pe resistance", "ground bond", "continuita terra")
LEAKAGE_KEYWORDS = ("equipment leakage", "dispersione", "leakage current")
APPLIED_PART_KEYWORDS = ("applied part leakage", "parte applicata", "patient leakage")
INSULATION_KEYWORDS = ("insulation", "isolamento")


def find_measurement_by_keywords(measurements: list[dict], keywords: list[str] | tuple[str, ...]) -> list[dict]:
    normalized = [normalize_text(keyword) for keyword in keywords]
    return [item for item in measurements if any(keyword in measurement_text(item) for keyword in normalized)]


def find_protective_earth_measurements(measurements: list[dict]) -> list[dict]:
    return find_measurement_by_keywords(measurements, PE_KEYWORDS)


def find_worst_protective_earth(measurements: list[dict]) -> dict | None:
    candidates = find_protective_earth_measurements(measurements)
    if not candidates:
        return None
    return max(candidates, key=_numeric_value)


def find_equipment_leakage_current(measurements: list[dict]) -> list[dict]:
    return find_measurement_by_keywords(measurements, LEAKAGE_KEYWORDS)


def find_applied_part_leakage(measurements: list[dict]) -> list[dict]:
    return find_measurement_by_keywords(measurements, APPLIED_PART_KEYWORDS)


def find_insulation_measurements(measurements: list[dict]) -> list[dict]:
    return find_measurement_by_keywords(measurements, INSULATION_KEYWORDS)


def _numeric_value(item: dict[str, Any]) -> float:
    raw = str(item.get("value") or item.get("valore") or item.get("raw") or "")
    match = re.search(r"-?\d+(?:[.,]\d+)?", raw)
    if not match:
        return float("-inf")
    return float(match.group(0).replace(",", "."))
