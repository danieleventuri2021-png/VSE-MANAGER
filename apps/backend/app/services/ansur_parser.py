from pathlib import Path
import re
import xml.etree.ElementTree as ET
from typing import Any

from app.services.ansur_template_detector import is_permanent_three_measure_template
from app.services.measurement_indexer import build_measurement_index
from app.services.xml_cleaner import read_xml_document_text


def parse_ansur_mtr(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    root = ET.fromstring(read_xml_document_text(file_path))
    items = _all_items(root)
    measurements = _measurements(root)
    template_name = _first_text(root, ("TemplateName", "ProcedureName", "TestTemplate", "Template")) or _attr_contains(root, "template")
    normalized = {
        "source_type": "mtr",
        "source_path": str(file_path),
        "dut": {
            "manufacturer": _item_value(items, ("manufacturer", "produttore", "marca")),
            "model": _item_value(items, ("model", "modello")),
            "serial_number": _item_value(items, ("serial", "serial number", "matricola", "s/n")),
            "inventory": _item_value(items, ("equipment number", "appliance code", "inventory", "inventario", "asset", "invgest")),
            "description": _item_value(items, ("other", "tipologia", "description", "descrizione", "device")),
            "location": _item_value(items, ("location", "stanza", "ubicazione")),
        },
        "ansur": {
            "template_name": template_name,
            "electrical_class": _find_text_any(root, ("Class", "ElectricalClass", "Classe")),
            "applied_part_type": _find_applied_part(root),
            "is_permanent_three_measure_template": False,
        },
        "test": {
            "date": _find_text_any(root, ("Date", "TestDate", "StartTime", "EndTime")),
            "status": _find_status(root),
        },
        "instrument": {
            "type": _find_text_contains(root, ("ESA615",)) or "ESA615",
            "manufacturer": _find_text_contains(root, ("Fluke",)) or "Fluke Biomedical",
            "serial_number": _find_text_any(root, ("InstrumentSerial", "AnalyzerSerial", "SerialNumber")),
            "calibration_date": _find_text_any(root, ("CalibrationDate", "CalDate", "Calibrazione")),
        },
        "measurements": measurements,
        "unrecognized": [],
    }
    normalized["ansur"]["is_permanent_three_measure_template"] = is_permanent_three_measure_template(template_name or "", measurements)
    normalized["measurement_index"] = build_measurement_index(measurements)
    return normalized


def _strip(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(element: ET.Element | None) -> str:
    return " ".join((element.text or "").split()) if element is not None else ""


def _all_items(root: ET.Element) -> list[dict[str, str]]:
    result = []
    for element in root.iter():
        if _strip(element.tag) != "item":
            continue
        attrs = {k.lower(): v for k, v in element.attrib.items()}
        name = attrs.get("name") or attrs.get("caption") or attrs.get("id") or _child_text(element, ("name", "caption", "id"))
        value = attrs.get("value") or _child_text(element, ("value", "text")) or _text(element)
        if name or value:
            result.append({"name": name, "value": value})
    return result


def _item_value(items: list[dict[str, str]], keys: tuple[str, ...]) -> str | None:
    for item in items:
        name = (item.get("name") or "").lower()
        if any(key in name for key in keys):
            return item.get("value") or None
    return None


def _measurements(root: ET.Element) -> list[dict[str, Any]]:
    result = []
    for element in root.iter():
        tag = _strip(element.tag)
        if tag not in {"resultitem", "measurement", "testelement"}:
            continue
        attrs = {k.lower(): v for k, v in element.attrib.items()}
        children = { _strip(child.tag): _text(child) for child in list(element) if _text(child)}
        name = attrs.get("name") or attrs.get("caption") or children.get("name") or children.get("caption") or tag
        value = attrs.get("value") or attrs.get("measuredvalue") or children.get("value") or children.get("measuredvalue") or _extract_value(_text(element))
        unit = attrs.get("unit") or children.get("unit") or _extract_unit(value or _text(element))
        result.append(
            {
                "name": name,
                "description": attrs.get("description") or children.get("description") or "",
                "parameter": attrs.get("parameter") or children.get("parameter") or "",
                "condition": attrs.get("condition") or children.get("condition") or "",
                "value": value or "",
                "unit": unit or "",
                "result": attrs.get("result") or attrs.get("status") or children.get("result") or children.get("status") or "",
                "element_id": attrs.get("elementid") or attrs.get("element_id") or children.get("elementid") or "",
                "test_element": attrs.get("testelement") or children.get("testelement") or "",
                "raw": ET.tostring(element, encoding="unicode")[:1000],
            }
        )
    return result


def _first_text(root: ET.Element, names: tuple[str, ...]) -> str | None:
    lowered = {name.lower() for name in names}
    for element in root.iter():
        if _strip(element.tag) in lowered and _text(element):
            return _text(element)
    return None


def _find_text_any(root: ET.Element, names: tuple[str, ...]) -> str | None:
    return _first_text(root, names) or _attr_named(root, names)


def _find_text_contains(root: ET.Element, needles: tuple[str, ...]) -> str | None:
    for element in root.iter():
        text = _text(element)
        if any(needle.lower() in text.lower() for needle in needles):
            return text
    return None


def _find_status(root: ET.Element) -> str | None:
    value = _find_text_any(root, ("Status", "Result", "OverallResult", "Esito"))
    if value:
        return value.upper()
    text = ET.tostring(root, encoding="unicode").lower()
    if "fail" in text or "failed" in text:
        return "FAIL"
    if "pass" in text or "conforme" in text:
        return "PASS"
    return None


def _find_applied_part(root: ET.Element) -> str | None:
    text = ET.tostring(root, encoding="unicode").upper()
    for token in ("CF", "BF", "B"):
        if re.search(rf"\b{token}\b", text):
            return token
    return None


def _child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    lowered = {name.lower() for name in names}
    for child in list(element):
        if _strip(child.tag) in lowered and _text(child):
            return _text(child)
    return ""


def _attr_named(root: ET.Element, names: tuple[str, ...]) -> str | None:
    lowered = {name.lower() for name in names}
    for element in root.iter():
        for key, value in element.attrib.items():
            if key.lower() in lowered and value:
                return value
    return None


def _attr_contains(root: ET.Element, needle: str) -> str | None:
    for element in root.iter():
        for key, value in element.attrib.items():
            if needle.lower() in key.lower() and value:
                return value
    return None


def _extract_value(text: str) -> str:
    match = re.search(r"-?\d+(?:[.,]\d+)?\s*(?:ohm|ma|ua|µa|v|mohm)?", text, re.IGNORECASE)
    return match.group(0) if match else ""


def _extract_unit(text: str) -> str:
    match = re.search(r"\b(ohm|ma|ua|µa|v|mohm)\b", text, re.IGNORECASE)
    return match.group(1) if match else ""
