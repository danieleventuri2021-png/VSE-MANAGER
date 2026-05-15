from pathlib import Path

from app.services.source_writer import save_to_source


def write_mtr_updates(path: str | Path, updates: dict) -> None:
    file_path = Path(path)
    backup_root = file_path.parent / ".gestione_vse_backups"
    save_to_source(file_path, updates, backup_root)
