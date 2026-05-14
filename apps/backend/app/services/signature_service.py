from pathlib import Path


def signature_exists(path: str | None) -> bool:
    return bool(path and Path(path).exists() and Path(path).is_file())
