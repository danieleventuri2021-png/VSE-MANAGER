from datetime import datetime
from pathlib import Path
import shutil


def create_backup(paths: list[str | Path], backup_root: str | Path, label: str) -> Path:
    root = Path(backup_root)
    target = root / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_safe(label)}"
    target.mkdir(parents=True, exist_ok=True)
    for item in paths:
        source = Path(item)
        if not source.exists():
            continue
        destination = target / source.name
        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)
    return target


def _safe(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)[:80] or "backup"
