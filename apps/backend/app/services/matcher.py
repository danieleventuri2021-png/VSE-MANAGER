import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

try:
    from rapidfuzz import fuzz
except ModuleNotFoundError:
    class _FallbackFuzz:
        @staticmethod
        def ratio(left: str, right: str) -> float:
            return SequenceMatcher(None, left, right).ratio() * 100

        @staticmethod
        def token_set_ratio(left: str, right: str) -> float:
            left_tokens = set(left.lower().split())
            right_tokens = set(right.lower().split())
            if not left_tokens or not right_tokens:
                return 0.0
            common = left_tokens & right_tokens
            combined_left = " ".join(sorted(common | (left_tokens - right_tokens)))
            combined_right = " ".join(sorted(common | (right_tokens - left_tokens)))
            return SequenceMatcher(None, combined_left, combined_right).ratio() * 100

    fuzz = _FallbackFuzz()


@dataclass
class MatchResult:
    equipment_index: int
    mtr_index: int | None
    status: str
    score: float
    reason: str


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "", str(value or "")).upper()


def match_records(equipment: list[dict], mtr_files: list[dict]) -> tuple[list[MatchResult], list[int]]:
    used: set[int] = set()
    results: list[MatchResult] = []
    for eq_index, eq in enumerate(equipment):
        best_index: int | None = None
        best_score = 0.0
        best_reason = "nessuna corrispondenza"
        for mtr_index, mtr in enumerate(mtr_files):
            if mtr_index in used:
                continue
            score, reason = score_pair(eq, mtr)
            if score > best_score:
                best_index, best_score, best_reason = mtr_index, score, reason
        if best_index is None or best_score < 55:
            results.append(MatchResult(eq_index, None, "mancante", best_score, best_reason))
            continue
        status = "certo" if best_score >= 90 else "da_controllare"
        used.add(best_index)
        results.append(MatchResult(eq_index, best_index, status, best_score, best_reason))
    orphan_indexes = [index for index in range(len(mtr_files)) if index not in used]
    return results, orphan_indexes


def score_pair(eq: dict, mtr: dict) -> tuple[float, str]:
    for field in ("matricola", "seriale"):
        left, right = normalize_key(eq.get(field)), normalize_key(mtr.get(field))
        if left and right and left == right:
            return 100.0, f"{field} esatta"
    exact_inventory = normalize_key(eq.get("inventario")) and normalize_key(eq.get("inventario")) == normalize_key(mtr.get("inventario"))
    if exact_inventory:
        return 92.0, "inventario esatto"
    serial_scores = []
    for field in ("matricola", "seriale"):
        left, right = normalize_key(eq.get(field)), normalize_key(mtr.get(field))
        if left and right:
            serial_scores.append(fuzz.ratio(left, right))
    serial_score = max(serial_scores) if serial_scores else 0.0
    descriptive_fields = ("produttore", "modello", "descrizione", "inventario")
    descriptive = [_field_score(eq, mtr, field) for field in descriptive_fields]
    fallback_score = sum(descriptive) / len(descriptive)
    score = max(float(serial_score), float(fallback_score * 0.85))
    reason = "fuzzy matricola/seriale" if serial_score >= fallback_score else "fallback descrittivo"
    return score, reason


def _field_score(eq: dict, mtr: dict, field: str) -> float:
    left = str(eq.get(field) or "")
    right = str(mtr.get(field) or "")
    if not left or not right:
        return 0.0
    return float(fuzz.token_set_ratio(left, right))
