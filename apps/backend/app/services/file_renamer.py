from pathlib import Path
import re


def build_mtr_filename(record: dict) -> str:
    parts = [
        record.get("matricola") or record.get("seriale") or "SENZA-MATRICOLA",
        record.get("produttore") or "PRODUTTORE",
        record.get("modello") or "MODELLO",
        record.get("reparto") or "REPARTO",
    ]
    return "-".join(_clean(part) for part in parts) + ".MTR"


def unique_path(folder: str | Path, filename: str) -> Path:
    folder_path = Path(folder)
    stem = Path(filename).stem
    suffix = Path(filename).suffix or ".MTR"
    candidate = folder_path / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = folder_path / f"{stem}_{counter:02d}{suffix}"
        counter += 1
    return candidate


def rename_mtr(source: str | Path, record: dict) -> tuple[Path, bool]:
    src = Path(source)
    destination = unique_path(src.parent, build_mtr_filename(record))
    conflict = destination.name != build_mtr_filename(record)
    if src.resolve() != destination.resolve():
        src.rename(destination)
    return destination, conflict


def _clean(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    text = re.sub(r"_+", "_", text).strip("._-")
    return text[:80] or "ND"
