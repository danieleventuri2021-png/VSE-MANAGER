from datetime import date, datetime
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import FileMtr, LavoroVse, RegistroApparecchiatura, VerificaVse
from app.services.bulk_pdf_service import build_final_pdf_data


def sync_job_registry(db: Session, job: LavoroVse) -> dict[str, Any]:
    files = db.query(FileMtr).filter(FileMtr.lavoro_id == job.id).order_by(FileMtr.id).all()
    created = 0
    updated = 0
    skipped = []
    for file_mtr in files:
        verification = file_mtr.verifiche[0] if file_mtr.verifiche else None
        data = build_final_pdf_data(job, file_mtr, verification)
        row_data = registry_data_from_pdf_data(job, file_mtr, verification, data)
        if not row_data["identificativo"]:
            skipped.append({"file_mtr_id": file_mtr.id, "reason": "identificativo mancante"})
            continue
        existing = find_existing_registry_equipment(db, row_data)
        if existing:
            for key, value in row_data.items():
                setattr(existing, key, value)
            updated += 1
        else:
            db.add(RegistroApparecchiatura(**row_data))
            created += 1
    return {"processed": len(files), "created": created, "updated": updated, "skipped": skipped}


def find_existing_registry_equipment(db: Session, row_data: dict[str, Any]) -> RegistroApparecchiatura | None:
    rows = (
        db.query(RegistroApparecchiatura)
        .filter(
            RegistroApparecchiatura.owner_user_id == row_data.get("owner_user_id"),
            RegistroApparecchiatura.cliente_nome == row_data["cliente_nome"],
        )
        .all()
    )
    ranked = sorted(
        ((registry_match_score(row, row_data), row) for row in rows),
        key=lambda item: item[0]["score"],
        reverse=True,
    )
    if not ranked or ranked[0][0]["score"] < 90:
        return None
    return ranked[0][1]


def registry_match_score(row: RegistroApparecchiatura, data: dict[str, Any]) -> dict[str, Any]:
    serials = {normalize_identifier(value) for value in (row.matricola, row.seriale, row.identificativo) if value}
    incoming_serials = {normalize_identifier(value) for value in (data.get("matricola"), data.get("seriale"), data.get("identificativo")) if value}
    inventories = {normalize_identifier(row.inventario_gestionale), normalize_identifier(row.inventario_ente)}
    incoming_inventories = {normalize_identifier(data.get("inventario_gestionale")), normalize_identifier(data.get("inventario_ente"))}
    inventories.discard("")
    incoming_inventories.discard("")
    if serials & incoming_serials:
        return {"score": 100, "reason": "matricola/seriale gia presente in archivio"}
    if inventories & incoming_inventories:
        return {"score": 96, "reason": "INVGEST/inventario gia presente in archivio"}
    return {"score": 0, "reason": "nessuna corrispondenza archivio"}


def registry_identity_match_score(row: RegistroApparecchiatura, data: dict[str, Any]) -> dict[str, Any]:
    serials = {normalize_identifier(value) for value in (row.matricola, row.seriale, row.identificativo) if value}
    incoming_serials = {normalize_identifier(value) for value in (data.get("matricola"), data.get("seriale"), data.get("identificativo")) if value}
    inventories = {normalize_identifier(row.inventario_gestionale), normalize_identifier(row.inventario_ente)}
    incoming_inventories = {normalize_identifier(data.get("inventario_gestionale")), normalize_identifier(data.get("inventario_ente"))}
    inventories.discard("")
    incoming_inventories.discard("")
    if serials & incoming_serials:
        return {"score": 100, "reason": "matricola/seriale uguale"}
    if inventories & incoming_inventories:
        return {"score": 96, "reason": "inventario uguale"}
    return {"score": 0, "reason": "nessuna identita certa"}


def registry_data_from_pdf_data(job: LavoroVse, file_mtr: FileMtr, verification: VerificaVse | None, data: dict) -> dict:
    periodicity = parse_periodicity_months(data.get("periodicita") or job.periodicita_default or "12")
    last_date = parse_date(data.get("testDate") or data.get("data_test") or data.get("data_verifica"))
    next_date = add_months(last_date, periodicity) if last_date and periodicity else None
    identifier = first_value(data.get("serial"), data.get("matricola"), data.get("seriale"), data.get("invGest"), data.get("inventario"), file_mtr.matricola, file_mtr.seriale, file_mtr.inventario)
    return {
        "cliente_nome": job.cliente_nome or "Cliente non indicato",
        "owner_user_id": getattr(job, "owner_user_id", None),
        "presidio": data.get("presidio") or "",
        "reparto": data.get("reparto") or "",
        "stanza": data.get("stanza") or "",
        "ubicazione": " - ".join(part for part in [data.get("presidio"), data.get("reparto"), data.get("stanza")] if part),
        "tipologia": data.get("tipologia") or data.get("descrizione") or file_mtr.descrizione,
        "produttore": data.get("manufacturer") or data.get("produttore") or file_mtr.produttore,
        "modello": data.get("model") or data.get("modello") or file_mtr.modello,
        "matricola": data.get("serial") or data.get("matricola") or file_mtr.matricola,
        "seriale": data.get("serial") or data.get("seriale") or file_mtr.seriale,
        "inventario_gestionale": data.get("invGest") or data.get("inventario") or file_mtr.inventario,
        "inventario_ente": data.get("invEnte") or data.get("inventario_ente") or "",
        "civab": data.get("civab") or "",
        "identificativo": normalize_identifier(identifier),
        "data_ultima_verifica": last_date.isoformat() if last_date else "",
        "periodicita_mesi": periodicity,
        "data_prossima_verifica": next_date.isoformat() if next_date else "",
        "esito_ultima_verifica": data.get("overallStatus") or data.get("esito_generale") or ((getattr(file_mtr, "parsed_json", {}) or {}).get("test", {}).get("status") if getattr(file_mtr, "parsed_json", None) else ""),
        "tecnico_ultima_verifica": data.get("tecnico") or "",
        "ultimo_lavoro_id": job.id,
        "ultimo_file_mtr_id": file_mtr.id,
        "ultima_verifica_id": verification.id if verification else None,
        "calendar_event_id": None,
        "raw_json": data,
    }


def build_registry_ics(rows: list[RegistroApparecchiatura]) -> str:
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//VSE-MANAGER//Scadenze VSE//IT"]
    for row in rows:
        if not row.data_prossima_verifica:
            continue
        dt = row.data_prossima_verifica.replace("-", "")
        summary = escape_ics(f"VSE {row.cliente_nome} - {row.tipologia or row.modello or row.identificativo}")
        description = escape_ics(
            f"Apparecchiatura: {row.tipologia or ''}\\nMarca: {row.produttore or ''}\\nModello: {row.modello or ''}\\nMatricola: {row.matricola or ''}\\nUbicazione: {row.ubicazione or ''}"
        )
        uid = f"vse-{row.id}-{row.identificativo}@vse-manager"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now}",
                f"DTSTART;VALUE=DATE:{dt}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{description}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def parse_periodicity_months(value: Any) -> int | None:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            pass
    return None


def add_months(start: date, months: int) -> date:
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def first_value(*values: Any) -> str:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return ""


def normalize_identifier(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(value or "")).upper()


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def escape_ics(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
