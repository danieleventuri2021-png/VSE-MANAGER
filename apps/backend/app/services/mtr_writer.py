from pathlib import Path


def write_mtr_updates(path: str | Path, updates: dict) -> None:
    file_path = Path(path)
    original = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = [original.rstrip(), "", "# Aggiornamento gestione-vse"]
    for key, value in updates.items():
        if value is not None:
            lines.append(f"{key}: {value}")
    file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
