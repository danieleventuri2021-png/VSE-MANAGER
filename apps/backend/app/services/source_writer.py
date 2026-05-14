from datetime import datetime
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from app.services.mtr_parser import parse_mtr_file


SAFE_FIELDS = {
    "produttore": ("manufacturer", "produttore", "marca"),
    "modello": ("model", "modello"),
    "matricola": ("serial", "serial number", "matricola", "s/n"),
    "inventario": ("inventory", "inventario", "asset"),
    "descrizione": ("description", "descrizione", "device"),
    "reparto": ("location", "ubicazione", "reparto", "presidio"),
}


def save_to_source(path: str | Path, updates: dict, backup_root: str | Path) -> dict:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Sorgente non trovato: {source}")
    updates = _normalize_updates(updates)
    backup_path = _backup(source, backup_root)
    if source.suffix.lower() == ".csv":
        changed = _save_csv(source, updates)
    else:
        changed = _save_xml_or_text_mtr(source, updates)
    parsed = parse_mtr_file(source)
    return {"source": str(source), "backup": str(backup_path), "changed": changed, "parsed": parsed}


def _backup(source: Path, backup_root: str | Path) -> Path:
    folder = Path(backup_root) / f"source_write_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source.name
    shutil.copy2(source, target)
    return target


def _normalize_updates(updates: dict) -> dict:
    aliases = {
        "produttore": ("produttore", "manufacturer"),
        "modello": ("modello", "model"),
        "matricola": ("matricola", "serial", "seriale"),
        "inventario": ("inventario", "invGest", "equipmentNumber"),
        "descrizione": ("descrizione", "tipologia", "other"),
        "reparto": ("reparto", "presidio", "location"),
    }
    normalized = {}
    for target, keys in aliases.items():
        for key in keys:
            if key in updates:
                normalized[target] = updates[key]
                break
    return {**updates, **normalized}


def _save_xml_or_text_mtr(source: Path, updates: dict) -> list[str]:
    content = source.read_text(encoding="utf-8", errors="ignore")
    if content.lstrip().startswith("<"):
        try:
            return _save_xml(source, updates)
        except ET.ParseError:
            pass
    return _save_key_value_text(source, updates)


def _save_xml(source: Path, updates: dict) -> list[str]:
    tree = ET.parse(source)
    root = tree.getroot()
    changed = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1].lower() != "item":
            continue
        name = " ".join(str(item.attrib.get(key, "")) for key in ("Name", "name", "Caption", "caption", "ID", "id")).lower()
        for field, aliases in SAFE_FIELDS.items():
            if field not in updates or not any(alias in name for alias in aliases):
                continue
            if "Value" in item.attrib:
                item.attrib["Value"] = str(updates[field])
            elif "value" in item.attrib:
                item.attrib["value"] = str(updates[field])
            else:
                item.text = str(updates[field])
            changed.append(field)
    tree.write(source, encoding="utf-8", xml_declaration=True)
    return changed


def _save_csv(source: Path, updates: dict) -> list[str]:
    return _save_key_value_text(source, updates, separators=r"[:=;,]")


def _save_key_value_text(source: Path, updates: dict, separators: str = r"[:=]") -> list[str]:
    lines = source.read_text(encoding="utf-8", errors="ignore").splitlines()
    changed = []
    output = []
    for line in lines:
        new_line = line
        for field, aliases in SAFE_FIELDS.items():
            if field not in updates:
                continue
            pattern = rf"^(\s*(?:{'|'.join(re.escape(alias) for alias in aliases)})\s*{separators}\s*)(.*)$"
            if re.match(pattern, line, flags=re.IGNORECASE):
                new_line = re.sub(pattern, rf"\g<1>{updates[field]}", line, flags=re.IGNORECASE)
                changed.append(field)
                break
        output.append(new_line)
    source.write_text("\n".join(output) + "\n", encoding="utf-8")
    return changed
