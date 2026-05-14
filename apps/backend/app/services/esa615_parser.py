from pathlib import Path
from typing import Any

from app.services.ansur_parser import parse_ansur_mtr


def parse_esa615_file(path: str | Path) -> dict[str, Any]:
    parsed = parse_ansur_mtr(path)
    parsed.setdefault("instrument", {})
    parsed["instrument"]["type"] = parsed["instrument"].get("type") or "ESA615"
    parsed["instrument"]["manufacturer"] = parsed["instrument"].get("manufacturer") or "Fluke Biomedical"
    return parsed
