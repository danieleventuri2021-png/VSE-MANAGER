from datetime import datetime
from pathlib import Path
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET

from app.services.mtr_parser import parse_mtr_file
from app.services.xml_cleaner import read_xml_document_text


SAFE_FIELDS = {
    "produttore": ("manufacturer", "produttore", "marca"),
    "modello": ("model", "modello"),
    "matricola": ("serial", "serial number", "matricola", "s/n"),
    "inventario": ("inventory", "inventario", "asset", "equipment number", "invgest", "appliance code"),
    "descrizione": ("description", "descrizione", "device", "other", "tipologia", "equipment"),
    "reparto": ("location", "ubicazione", "reparto", "presidio"),
}


def save_to_source(path: str | Path, updates: dict, backup_root: str | Path) -> dict:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Sorgente non trovato: {source}")
    updates = _normalize_updates(updates)
    backup_path = _backup(source, backup_root)
    try:
        if source.suffix.lower() == ".csv":
            changed = _save_csv(source, updates)
        else:
            changed = _save_xml_or_text_mtr(source, updates)
    except Exception:
        _restore_from_backup(backup_path, source)
        raise
    parsed = parse_mtr_file(source)
    return {"source": str(source), "backup": str(backup_path), "changed": changed, "parsed": parsed}


def _restore_from_backup(backup_path: Path, source: Path) -> None:
    if backup_path.exists():
        shutil.copy2(backup_path, source)


def _atomic_write_bytes(target: Path, data: bytes) -> None:
    target_dir = target.parent
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target_dir))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _atomic_write_text(target: Path, text: str, encoding: str = "utf-8") -> None:
    _atomic_write_bytes(target, text.encode(encoding))


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
    if content.lstrip("\ufeff\r\n\t ").startswith("<"):
        try:
            return _save_xml(source, updates)
        except ET.ParseError:
            pass
    return _save_key_value_text(source, updates)


def _save_xml(source: Path, updates: dict) -> list[str]:
    root = ET.fromstring(read_xml_document_text(source))
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
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    _atomic_write_bytes(source, payload)
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
            pattern = rf"^(\s*(?:{'|'.join(re.escape(alias) for alias in aliases)})\s*(?:{separators}\s*)+)(.*)$"
            if re.match(pattern, line, flags=re.IGNORECASE):
                new_line = re.sub(pattern, rf"\g<1>{updates[field]}", line, flags=re.IGNORECASE)
                changed.append(field)
                break
        output.append(new_line)
    _atomic_write_text(source, "\n".join(output) + "\n")
    return changed
