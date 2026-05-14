import re
import unicodedata
from collections import defaultdict
from typing import Any


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def build_measurement_index(measurements: list[dict]) -> dict:
    index: dict[str, Any] = {"items": measurements, "by_name": defaultdict(list), "by_unit": defaultdict(list), "by_result": defaultdict(list), "by_element_id": defaultdict(list)}
    for position, item in enumerate(measurements):
        tokens = {
            "name": normalize_text(item.get("name") or item.get("nome")),
            "description": normalize_text(item.get("description") or item.get("descrizione")),
            "parameter": normalize_text(item.get("parameter")),
            "condition": normalize_text(item.get("condition")),
            "result": normalize_text(item.get("result") or item.get("esito")),
            "unit": normalize_text(item.get("unit") or item.get("unita")),
            "element_id": normalize_text(item.get("element_id") or item.get("ElementID")),
            "test_element": normalize_text(item.get("test_element") or item.get("TestElement")),
        }
        item["_index"] = position
        item["_tokens"] = tokens
        for key in ("name", "description", "parameter", "condition", "test_element"):
            for token in tokens[key].split():
                index["by_name"][token].append(position)
        if tokens["unit"]:
            index["by_unit"][tokens["unit"]].append(position)
        if tokens["result"]:
            index["by_result"][tokens["result"]].append(position)
        if tokens["element_id"]:
            index["by_element_id"][tokens["element_id"]].append(position)
    return {key: dict(value) if hasattr(value, "items") else value for key, value in index.items()}


def measurement_text(item: dict) -> str:
    tokens = item.get("_tokens") or {}
    if tokens:
        return " ".join(str(tokens.get(key, "")) for key in ("name", "description", "parameter", "condition", "test_element"))
    return " ".join(
        normalize_text(item.get(key))
        for key in ("name", "nome", "description", "descrizione", "parameter", "condition", "test_element", "raw")
    )
