import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models import FileMtr, LavoroVse, PdfGenerato, VerificaVse
from app.services.pdf_generator import generate_vse_pdf, to_legacy_edited
from app.services.vse_defaults import ansur_defaults, job_defaults, merge_final_data, source_data

logger = logging.getLogger(__name__)


def build_final_pdf_data(job: LavoroVse, file_mtr: FileMtr, verification: VerificaVse | None = None) -> dict[str, Any]:
    parsed = file_mtr.parsed_json or file_mtr.parsed_data.get("normalized") if file_mtr.parsed_data else {}
    parsed = parsed or {}
    legacy = parsed.get("legacy") or {}
    file_fallback = {
        "produttore": file_mtr.produttore or "",
        "modello": file_mtr.modello or "",
        "matricola": file_mtr.matricola or file_mtr.seriale or "",
        "seriale": file_mtr.seriale or "",
        "inventario": file_mtr.inventario or "",
        "descrizione": file_mtr.descrizione or "",
        "reparto": file_mtr.reparto or "",
        "template_ansur": file_mtr.template_ansur or "",
        "nome_file": file_mtr.nome_file,
        "path_corrente": file_mtr.path_corrente,
    }
    excel = verification.dati_excel_json if verification else {}
    revised = verification.dati_revisionati_json if verification else {}
    locked = {key: revised.get(key) for key, is_locked in (verification.campi_bloccati_json or {}).items() if is_locked} if verification else {}
    parsed_source = source_data(parsed)
    legacy_source = {
        "source_file": legacy.get("sourceFile", ""),
        "source_path": legacy.get("sourceFilePath", ""),
        "serialNumber": legacy.get("serialNumber", ""),
        "equipmentNumber": legacy.get("equipmentNumber", ""),
        "manufacturer": legacy.get("manufacturer", ""),
        "model": legacy.get("model", ""),
        "location": legacy.get("location", ""),
        "other": legacy.get("other", ""),
        "tipologia": legacy.get("tipologia") or legacy.get("other", ""),
        "templateName": legacy.get("templateName", ""),
        "classification": legacy.get("classification", ""),
        "apType": legacy.get("apType", ""),
        "testDate": legacy.get("testDate", ""),
        "overallStatus": legacy.get("overallStatus", ""),
        "instrument": legacy.get("instrument") or {},
        "measurements": legacy.get("measurements") or parsed.get("measurements") or [],
    }
    combined_source = {**file_fallback, **{key: value for key, value in legacy_source.items() if value not in (None, "")}}
    combined_source.update({key: value for key, value in parsed_source.items() if value not in (None, "")})
    final = merge_final_data(
        job_defaults_data=job_defaults(job),
        ansur_data={**combined_source, **ansur_defaults(parsed), "measurements": parsed.get("measurements") or []},
        excel_data=excel or {},
        revised_data=revised or {},
        locked_data=locked or {},
    )
    if verification:
        direct_fields = ("tecnico", "firma_path", "proprieta", "periodicita", "tensione", "frequenza", "potenza", "potenza_unita", "protezione", "installazione", "mobilita", "classe_elettrica", "parte_applicata", "note")
        for field in direct_fields:
            value = getattr(verification, field, None)
            if value not in (None, ""):
                final[field] = value
    final = {**to_legacy_edited(final), **final}
    return final


def generate_one_pdf(db: Session, job: LavoroVse, file_mtr: FileMtr, output_dir: str | Path) -> dict:
    verification = _verification_for_file(db, file_mtr)
    data = build_final_pdf_data(job, file_mtr, verification)
    header = _header_path(job)
    generated = generate_vse_pdf(data, output_dir, job.template_pdf or "standard", header)
    row = PdfGenerato(lavoro_id=job.id, verifica_id=verification.id if verification else None, file_mtr_id=file_mtr.id, percorso_pdf=generated["path"], nome_pdf=generated["filename"], template_pdf=generated["template_pdf"], esito="generato")
    db.add(row)
    if verification:
        verification.dati_finali_pdf_json = data
    return generated


def generate_all_pdfs(db: Session, job: LavoroVse, output_dir: str | Path) -> dict:
    report = {"total": 0, "generated": 0, "errors": [], "skipped": [], "anomalies": []}
    files = (
        db.query(FileMtr)
        .options(selectinload(FileMtr.verifiche), selectinload(FileMtr.matched_apparecchiature))
        .filter(FileMtr.lavoro_id == job.id)
        .order_by(FileMtr.id)
        .all()
    )
    report["total"] = len(files)
    for file_mtr in files:
        try:
            generate_one_pdf(db, job, file_mtr, output_dir)
            db.commit()
            report["generated"] += 1
        except Exception as exc:
            db.rollback()
            logger.exception("Errore generazione PDF per file_mtr_id=%s", file_mtr.id)
            report["errors"].append({"file_mtr_id": file_mtr.id, "error": str(exc)})
    return report


def _verification_for_file(db: Session, file_mtr: FileMtr) -> VerificaVse | None:
    if file_mtr.verifiche:
        return file_mtr.verifiche[0]
    equipment = file_mtr.matched_apparecchiature[0] if file_mtr.matched_apparecchiature else None
    if not equipment:
        return None
    verification = VerificaVse(file_mtr_id=file_mtr.id, apparecchiatura_id=equipment.id, dati_ansur_json=file_mtr.parsed_json or {}, dati_excel_json=equipment.raw_data or {})
    db.add(verification)
    db.flush()
    return verification


def _header_path(job: LavoroVse) -> str | None:
    root = Path(__file__).resolve().parents[4]
    name = "intestazione-consip-vse.png" if (job.intestazione_pdf or "").lower() == "consip" else "meditech-vse.png"
    custom = (job.intestazione_pdf or "").strip()
    if custom and custom.lower() not in {"standard", "consip"} and Path(custom).exists():
        return custom
    for candidate in (root / name, root / "data" / "templates" / name):
        if candidate.exists():
            return str(candidate)
    return None
