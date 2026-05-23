from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models import Apparecchiatura, FileMtr, LavoroVse, PdfGenerato
from app.services.equipment_registry_service import normalize_identifier


@dataclass(frozen=True)
class MeasurementKey:
    owner_user_id: int | None
    cliente_nome: str
    identificativo: str
    data_verifica: str


def filter_duplicate_measurement_files(db: Session, job: LavoroVse, parsed_files: list[dict]) -> tuple[list[dict], list[dict]]:
    existing_keys = _existing_measurement_keys(db, job)
    kept_by_key: dict[MeasurementKey, dict] = {}
    skipped: list[dict] = []

    for parsed in parsed_files:
        key = measurement_key_from_parsed(job, parsed)
        if not key:
            kept_by_key[object()] = parsed
            continue
        if key in existing_keys:
            skipped.append(_skip_item(parsed, key, "misura gia presente nel database"))
            continue
        current = kept_by_key.get(key)
        if current is None:
            kept_by_key[key] = parsed
            continue
        if measurement_count(parsed) > measurement_count(current):
            skipped.append(_skip_item(current, key, "duplicato nello stesso import"))
            kept_by_key[key] = parsed
        else:
            skipped.append(_skip_item(parsed, key, "duplicato nello stesso import"))

    return list(kept_by_key.values()), skipped


def cleanup_duplicate_measurement_files(db: Session, owner_user_id: int | None = None) -> dict[str, Any]:
    query = db.query(FileMtr).options(joinedload(FileMtr.lavoro), joinedload(FileMtr.verifiche))
    if owner_user_id is not None:
        query = query.join(LavoroVse, FileMtr.lavoro_id == LavoroVse.id).filter(LavoroVse.owner_user_id == owner_user_id)
    groups: dict[MeasurementKey, list[FileMtr]] = {}
    for file_mtr in query.order_by(FileMtr.id).all():
        if not file_mtr.lavoro:
            continue
        key = measurement_key_from_file(file_mtr)
        if key:
            groups.setdefault(key, []).append(file_mtr)

    removed = []
    for key, rows in groups.items():
        if len(rows) < 2:
            continue
        keep = max(rows, key=lambda row: (measurement_count(row.parsed_data or row.parsed_json or {}), row.created_at or datetime.min, row.id))
        for duplicate in rows:
            if duplicate.id == keep.id:
                continue
            db.query(Apparecchiatura).filter(Apparecchiatura.matched_file_mtr_id == duplicate.id).update({"matched_file_mtr_id": keep.id})
            for pdf in db.query(PdfGenerato).filter(PdfGenerato.file_mtr_id == duplicate.id).all():
                db.delete(pdf)
            removed.append(
                {
                    "file_mtr_id": duplicate.id,
                    "kept_file_mtr_id": keep.id,
                    "nome_file": duplicate.nome_file,
                    "identificativo": key.identificativo,
                    "data_verifica": key.data_verifica,
                    "misure": measurement_count(duplicate.parsed_data or duplicate.parsed_json or {}),
                }
            )
            db.delete(duplicate)
    return {"groups": sum(1 for rows in groups.values() if len(rows) > 1), "deleted": len(removed), "removed": removed}


def measurement_key_from_parsed(job: LavoroVse, parsed: dict) -> MeasurementKey | None:
    identifier = _parsed_identifier(parsed)
    test_date = normalized_measurement_date(_parsed_date(parsed))
    if not identifier or not test_date:
        return None
    return MeasurementKey(job.owner_user_id, _clean_client(job.cliente_nome), identifier, test_date)


def measurement_key_from_file(file_mtr: FileMtr) -> MeasurementKey | None:
    job = file_mtr.lavoro
    if not job:
        return None
    parsed = file_mtr.parsed_data or {}
    identifier = normalize_identifier(file_mtr.matricola or file_mtr.seriale or file_mtr.inventario) or _parsed_identifier(parsed)
    test_date = normalized_measurement_date(_parsed_date(parsed) or _parsed_date(file_mtr.parsed_json or {}))
    if not identifier or not test_date:
        return None
    return MeasurementKey(job.owner_user_id, _clean_client(job.cliente_nome), identifier, test_date)


def normalized_measurement_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("T", " ")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:19], fmt).date().isoformat()
        except ValueError:
            pass
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1))).isoformat()
    return ""


def measurement_count(data: dict) -> int:
    normalized = data.get("normalized") or data
    measurements = normalized.get("measurements") or data.get("misure") or []
    return len(measurements)


def _existing_measurement_keys(db: Session, job: LavoroVse) -> set[MeasurementKey]:
    query = (
        db.query(FileMtr)
        .options(joinedload(FileMtr.lavoro))
        .join(LavoroVse, FileMtr.lavoro_id == LavoroVse.id)
        .filter(LavoroVse.owner_user_id == job.owner_user_id, LavoroVse.cliente_nome == job.cliente_nome, LavoroVse.id != job.id)
    )
    return {key for row in query.all() if (key := measurement_key_from_file(row))}


def _skip_item(parsed: dict, key: MeasurementKey, reason: str) -> dict:
    return {
        "nome_file": parsed.get("nome_file") or "",
        "identificativo": key.identificativo,
        "data_verifica": key.data_verifica,
        "reason": reason,
        "misure": measurement_count(parsed),
    }


def _parsed_identifier(parsed: dict) -> str:
    normalized = parsed.get("normalized") or parsed
    dut = normalized.get("dut") or {}
    return normalize_identifier(
        parsed.get("matricola")
        or parsed.get("seriale")
        or parsed.get("inventario")
        or dut.get("serial_number")
        or dut.get("inventory")
    )


def _parsed_date(parsed: dict) -> Any:
    normalized = parsed.get("normalized") or parsed
    test = normalized.get("test") or {}
    legacy = normalized.get("legacy") or {}
    return test.get("date") or legacy.get("testDate") or parsed.get("data_verifica") or parsed.get("data_test") or parsed.get("testDate")


def _clean_client(value: Any) -> str:
    return str(value or "Cliente non indicato").strip() or "Cliente non indicato"
