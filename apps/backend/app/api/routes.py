from pathlib import Path
import shutil
from datetime import datetime
import re

from fastapi import APIRouter, Body, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Anomalia, Apparecchiatura, FileMtr, LavoroVse, LogOperativo, PdfGenerato, RegistroApparecchiatura, VerificaVse
from app.schemas.jobs import ApplyResult, FolderRequest, JobCreate, JobRead, PdfGenerateRequest, SystemPorts
from app.services.anomaly_service import create_anomaly
from app.services.backup_service import create_backup
from app.services.bulk_pdf_service import build_final_pdf_data, generate_all_pdfs, generate_one_pdf
from app.services.equipment_registry_service import build_registry_ics, sync_job_registry
from app.services.equipment_registry_service import normalize_identifier as normalize_registry_identifier
from app.services.difference_analyzer import analyze_differences
from app.services.excel_importer import import_excel
from app.services.file_renamer import rename_mtr
from app.services.log_service import log_event
from app.services.matcher import match_records
from app.services.mtr_parser import scan_mtr_folder
from app.services.mtr_writer import write_mtr_updates
from app.services.port_checker import check_ports
from app.services.session_defaults_service import apply_defaults_to_verification, update_job_defaults
from app.services.source_writer import save_to_source
from app.services.vse_defaults import ansur_defaults, job_defaults, source_data

router = APIRouter()

EQUIPMENT_FIELDS = ("row_index", "matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto", "raw_data")


@router.get("/system/ports", response_model=SystemPorts)
def system_ports():
    settings = get_settings()
    return check_ports(settings.backend_port, int(settings.frontend_origin.rsplit(":", 1)[-1]))


@router.get("/system/folders")
def browse_folders(path: str | None = None):
    if not path:
        roots = _folder_roots()
        return {"path": "", "parent": None, "folders": roots}
    current = Path(path).expanduser()
    if not current.exists() or not current.is_dir():
        raise HTTPException(status_code=404, detail="Cartella non trovata")
    folders = []
    try:
        for child in sorted(current.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir():
                folders.append({"name": child.name, "path": str(child)})
    except PermissionError:
        raise HTTPException(status_code=403, detail="Accesso alla cartella non consentito")
    parent = str(current.parent) if current.parent != current else ""
    return {"path": str(current), "parent": parent, "folders": folders}


@router.post("/system/folders")
def create_folder(payload: dict = Body(...)):
    parent = Path(str(payload.get("parent") or "")).expanduser()
    name = str(payload.get("name") or "").strip()
    if not parent.exists() or not parent.is_dir():
        raise HTTPException(status_code=404, detail="Cartella padre non trovata")
    if not name or any(part in name for part in ("\\", "/", ":")):
        raise HTTPException(status_code=400, detail="Nome cartella non valido")
    target = parent / name
    if target.exists():
        raise HTTPException(status_code=409, detail="Cartella gia esistente")
    target.mkdir()
    return {"path": str(target), "name": target.name}


@router.put("/system/folders")
def rename_folder(payload: dict = Body(...)):
    current = Path(str(payload.get("path") or "")).expanduser()
    name = str(payload.get("name") or "").strip()
    if not current.exists() or not current.is_dir():
        raise HTTPException(status_code=404, detail="Cartella non trovata")
    if not name or any(part in name for part in ("\\", "/", ":")):
        raise HTTPException(status_code=400, detail="Nome cartella non valido")
    target = current.parent / name
    if target.exists():
        raise HTTPException(status_code=409, detail="Esiste gia una cartella con questo nome")
    current.rename(target)
    return {"path": str(target), "name": target.name}


@router.delete("/system/folders")
def delete_folder(path: str):
    current = Path(path).expanduser()
    if not current.exists() or not current.is_dir():
        raise HTTPException(status_code=404, detail="Cartella non trovata")
    try:
        current.rmdir()
    except OSError:
        raise HTTPException(status_code=400, detail="La cartella non e vuota")
    return {"deleted": str(current)}


@router.post("/jobs", response_model=JobRead)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    job = LavoroVse(titolo=payload.titolo, cliente_nome=payload.cliente_nome, mtr_folder=payload.mtr_folder)
    db.add(job)
    db.flush()
    log_event(db, "job_created", f"Lavoro creato: {payload.titolo}", lavoro_id=job.id)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(db: Session = Depends(get_db)):
    return db.query(LavoroVse).order_by(LavoroVse.created_at.desc()).all()


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    return _job_or_404(db, job_id)


@router.post("/jobs/{job_id}/excel", response_model=JobRead)
def upload_excel(job_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    settings = get_settings()
    target_dir = Path(settings.input_dir) / f"job_{job_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (file.filename or "import.xlsx")
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    records, mapping = import_excel(target)
    db.query(Apparecchiatura).filter(Apparecchiatura.lavoro_id == job_id).delete()
    for record in records:
        equipment_data = {field: record.get(field) for field in EQUIPMENT_FIELDS}
        equipment = Apparecchiatura(lavoro_id=job_id, **equipment_data)
        db.add(equipment)
        if record.get("esito") or record.get("data_verifica"):
            db.add(VerificaVse(apparecchiatura=equipment, esito_excel=record.get("esito"), data_verifica=record.get("data_verifica")))
    job.excel_path = str(target)
    job.stato = "excel_importato"
    job.summary = {**job.summary, "excel_rows": len(records), "column_mapping": mapping}
    log_event(db, "excel_imported", f"Importate {len(records)} righe Excel", lavoro_id=job_id, dettagli={"mapping": mapping})
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/mtr-folder", response_model=JobRead)
def import_mtr_folder(job_id: int, payload: FolderRequest, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    parsed_files = scan_mtr_folder(payload.folder_path)
    db.query(FileMtr).filter(FileMtr.lavoro_id == job_id).delete()
    for parsed in parsed_files:
        db.add(
            FileMtr(
                lavoro_id=job_id,
                path_originale=parsed["path"],
                path_corrente=parsed["path"],
                nome_file=parsed["nome_file"],
                matricola=parsed.get("matricola"),
                seriale=parsed.get("seriale"),
                inventario=parsed.get("inventario"),
                produttore=parsed.get("produttore"),
                modello=parsed.get("modello"),
                descrizione=parsed.get("descrizione"),
                reparto=parsed.get("reparto"),
                parsed_data=parsed,
                source_type=(parsed.get("normalized") or {}).get("source_type", "mtr"),
                template_ansur=parsed.get("template_ansur"),
                is_permanent_three_measure_template=bool(parsed.get("is_permanent_three_measure_template")),
                parsed_json=parsed.get("normalized") or {},
                measurement_index_json=parsed.get("measurement_index") or {},
            )
        )
    job.mtr_folder = payload.folder_path
    job.stato = "mtr_importati"
    job.summary = {**job.summary, "mtr_files": len(parsed_files)}
    log_event(db, "mtr_imported", f"Importati {len(parsed_files)} file MTR", lavoro_id=job_id)
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/analyze", response_model=JobRead)
def analyze_job(job_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    equipment_rows = db.query(Apparecchiatura).filter(Apparecchiatura.lavoro_id == job_id).order_by(Apparecchiatura.row_index).all()
    mtr_rows = db.query(FileMtr).filter(FileMtr.lavoro_id == job_id).order_by(FileMtr.id).all()
    matches, orphans = match_records([_equipment_dict(row) for row in equipment_rows], [_mtr_dict(row) for row in mtr_rows])
    db.query(Anomalia).filter(Anomalia.lavoro_id == job_id).delete()
    counts = {"certo": 0, "da_controllare": 0, "mancante": 0, "mtr_orfano": len(orphans), "differenze": 0}
    for match in matches:
        eq = equipment_rows[match.equipment_index]
        eq.match_status = match.status
        eq.match_score = match.score
        if match.mtr_index is not None:
            mtr = mtr_rows[match.mtr_index]
            eq.matched_file_mtr_id = mtr.id
            verification = eq.verifiche[0] if eq.verifiche else VerificaVse(apparecchiatura=eq)
            if not eq.verifiche:
                db.add(verification)
            verification.file_mtr_id = mtr.id
            verification.dati_ansur_json = mtr.parsed_json or {}
            verification.dati_excel_json = eq.raw_data or {}
            defaults = ansur_defaults(mtr.parsed_json or {})
            verification.classe_elettrica = verification.classe_elettrica or defaults.get("classe_elettrica")
            verification.parte_applicata = verification.parte_applicata or defaults.get("parte_applicata")
            verification.installazione = verification.installazione or defaults.get("installazione")
            verification.mobilita = verification.mobilita or defaults.get("mobilita")
            mtr.stato = "abbinato" if match.status == "certo" else "da_controllare"
            differences = analyze_differences(_equipment_dict(eq), _mtr_dict(mtr))
            if differences["fields"]:
                counts["differenze"] += len(differences["fields"])
                create_anomaly(db, job_id, "differenza_excel_mtr", "Differenze tra Excel e MTR", "warning", {"equipment_id": eq.id, "mtr_id": mtr.id, "fields": differences["fields"]})
        else:
            eq.matched_file_mtr_id = None
            create_anomaly(db, job_id, "mtr_mancante", "Nessun file MTR associato alla riga Excel", "error", {"equipment_id": eq.id, "score": match.score})
        counts[match.status] += 1
    for index in orphans:
        mtr_rows[index].stato = "mtr_orfano"
        create_anomaly(db, job_id, "mtr_orfano", "File MTR non associato ad alcuna riga Excel", "info", {"mtr_id": mtr_rows[index].id})
    job.stato = "analizzato"
    job.summary = {**job.summary, **counts}
    log_event(db, "job_analyzed", "Analisi completata", lavoro_id=job_id, dettagli=counts)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}/matches")
def get_matches(job_id: int, db: Session = Depends(get_db)):
    _job_or_404(db, job_id)
    rows = db.query(Apparecchiatura).filter(Apparecchiatura.lavoro_id == job_id).order_by(Apparecchiatura.row_index).all()
    return [
        {
            "equipment": _equipment_dict(row),
            "status": row.match_status,
            "score": row.match_score,
            "mtr": _mtr_dict(row.matched_file_mtr) if row.matched_file_mtr else None,
        }
        for row in rows
    ]


@router.get("/jobs/{job_id}/anomalies")
def get_anomalies(job_id: int, db: Session = Depends(get_db)):
    _job_or_404(db, job_id)
    return db.query(Anomalia).filter(Anomalia.lavoro_id == job_id).order_by(Anomalia.created_at.desc()).all()


@router.get("/anomalies")
def list_all_anomalies(stato: str | None = "aperta", db: Session = Depends(get_db)):
    query = db.query(Anomalia).join(LavoroVse, Anomalia.lavoro_id == LavoroVse.id)
    if stato:
        query = query.filter(Anomalia.stato == stato)
    rows = query.order_by(LavoroVse.titolo, Anomalia.created_at.desc()).all()
    return [_anomaly_dict(row) for row in rows]


@router.delete("/anomalies/{anomaly_id}")
def delete_anomaly(anomaly_id: int, db: Session = Depends(get_db)):
    row = db.get(Anomalia, anomaly_id)
    if not row:
        raise HTTPException(status_code=404, detail="Anomalia non trovata")
    db.delete(row)
    db.commit()
    return {"deleted": anomaly_id}


@router.delete("/anomalies")
def delete_all_anomalies(stato: str | None = "aperta", db: Session = Depends(get_db)):
    query = db.query(Anomalia)
    if stato:
        query = query.filter(Anomalia.stato == stato)
    deleted = query.delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


@router.post("/jobs/{job_id}/apply", response_model=ApplyResult)
def apply_job(job_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    settings = get_settings()
    matched = db.query(Apparecchiatura).filter(Apparecchiatura.lavoro_id == job_id, Apparecchiatura.matched_file_mtr_id.isnot(None)).all()
    paths = [row.matched_file_mtr.path_corrente for row in matched if row.matched_file_mtr]
    backup_dir = create_backup(paths, settings.backup_dir, f"job_{job_id}")
    renamed: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    for row in matched:
        mtr = row.matched_file_mtr
        if not mtr:
            continue
        record = _equipment_dict(row)
        write_mtr_updates(mtr.path_corrente, record)
        new_path, conflict = rename_mtr(mtr.path_corrente, record)
        old_path = mtr.path_corrente
        mtr.path_corrente = str(new_path)
        mtr.nome_file = new_path.name
        renamed.append({"from": old_path, "to": str(new_path)})
        if conflict:
            conflicts.append({"from": old_path, "to": str(new_path)})
    job.stato = "applicato"
    job.summary = {**job.summary, "renamed": len(renamed), "rename_conflicts": len(conflicts), "last_backup": str(backup_dir)}
    log_event(db, "changes_applied", "Aggiornamenti MTR applicati", lavoro_id=job_id, dettagli={"backup_dir": str(backup_dir), "renamed": len(renamed)})
    db.commit()
    return ApplyResult(backup_dir=str(backup_dir), renamed=renamed, conflicts=conflicts)


@router.get("/jobs/{job_id}/logs")
def get_logs(job_id: int, db: Session = Depends(get_db)):
    _job_or_404(db, job_id)
    return db.query(LogOperativo).filter(LogOperativo.lavoro_id == job_id).order_by(LogOperativo.created_at.desc()).all()


@router.put("/jobs/{job_id}/settings", response_model=JobRead)
def update_job_settings(job_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    update_job_defaults(job, payload)
    log_event(db, "job_defaults_updated", "Default lavoro aggiornati", lavoro_id=job_id, dettagli=payload)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}/review")
def get_review_list(job_id: int, db: Session = Depends(get_db)):
    _job_or_404(db, job_id)
    files = db.query(FileMtr).filter(FileMtr.lavoro_id == job_id).order_by(FileMtr.id).all()
    return [_review_summary(db, file_mtr) for file_mtr in files]


@router.get("/jobs/{job_id}/review/{file_mtr_id}")
def get_review_detail(job_id: int, file_mtr_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    file_mtr = _file_or_404(db, file_mtr_id, job_id)
    verification = _ensure_verification(db, file_mtr)
    final = build_final_pdf_data(job, file_mtr, verification)
    verification.dati_finali_pdf_json = final
    db.commit()
    return {
        "file": _mtr_dict(file_mtr),
        "verification": _verification_dict(verification),
        "source": source_data(file_mtr.parsed_json or {}),
        "excel": verification.dati_excel_json or {},
        "final": final,
        "differences": analyze_differences(verification.dati_excel_json or {}, source_data(file_mtr.parsed_json or {})),
        "badges": _field_badges(verification, final),
    }


@router.put("/jobs/{job_id}/review/{file_mtr_id}")
def save_review_detail(job_id: int, file_mtr_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    file_mtr = _file_or_404(db, file_mtr_id, job_id)
    verification = _ensure_verification(db, file_mtr)
    revised = payload.get("dati_revisionati") or payload.get("fields") or {}
    locked = payload.get("campi_bloccati") or {}
    verification.dati_revisionati_json = {**(verification.dati_revisionati_json or {}), **revised}
    verification.campi_bloccati_json = {**(verification.campi_bloccati_json or {}), **locked}
    for field in ("tecnico", "firma_path", "proprieta", "periodicita", "tensione", "frequenza", "potenza", "potenza_unita", "protezione", "installazione", "mobilita", "classe_elettrica", "parte_applicata", "note"):
        if field in revised:
            setattr(verification, field, revised[field])
    verification.stato_revisione = payload.get("stato_revisione") or "revisionato"
    verification.dati_finali_pdf_json = build_final_pdf_data(job, file_mtr, verification)
    log_event(db, "review_saved", f"Revisione salvata per {file_mtr.nome_file}", lavoro_id=job_id, dettagli={"file_mtr_id": file_mtr_id})
    db.commit()
    return _verification_dict(verification)


@router.post("/jobs/{job_id}/apply-defaults")
def apply_job_defaults(job_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    if payload.get("save_as_job_default"):
        update_job_defaults(job, payload.get("values") or {})
    changed = []
    for file_mtr in db.query(FileMtr).filter(FileMtr.lavoro_id == job_id).all():
        verification = _ensure_verification(db, file_mtr)
        fields = apply_defaults_to_verification(job, verification, payload.get("values") or {})
        if fields:
            changed.append({"file_mtr_id": file_mtr.id, "fields": fields})
    log_event(db, "job_defaults_applied", "Default lavoro applicati agli MTR non bloccati", lavoro_id=job_id, dettagli={"changed": len(changed)})
    db.commit()
    return {"updated": len(changed), "items": changed}


@router.post("/files/{file_mtr_id}/save-source")
def save_source(file_mtr_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)):
    file_mtr = db.get(FileMtr, file_mtr_id)
    if not file_mtr:
        raise HTTPException(status_code=404, detail="File MTR non trovato")
    settings = get_settings()
    verification = _ensure_verification(db, file_mtr)
    updates = payload.get("fields") or verification.dati_revisionati_json or {}
    result = save_to_source(file_mtr.path_corrente, updates, settings.backup_dir)
    parsed = result["parsed"]
    file_mtr.parsed_data = parsed
    file_mtr.parsed_json = parsed.get("normalized") or {}
    file_mtr.measurement_index_json = parsed.get("measurement_index") or {}
    file_mtr.last_source_write_at = datetime.utcnow()
    log_event(db, "source_saved", "Campi identificativi salvati nel sorgente", lavoro_id=file_mtr.lavoro_id, dettagli={"file_mtr_id": file_mtr_id, "changed": result["changed"], "backup": result["backup"]})
    db.commit()
    return {"changed": result["changed"], "backup": result["backup"]}


@router.post("/jobs/{job_id}/pdf/generate-one/{file_mtr_id}")
def generate_pdf_one(job_id: int, file_mtr_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    file_mtr = _file_or_404(db, file_mtr_id, job_id)
    settings = get_settings()
    result = generate_one_pdf(db, job, file_mtr, Path(settings.output_dir) / f"job_{job_id}")
    log_event(db, "pdf_generated", f"PDF generato: {result['filename']}", lavoro_id=job_id, dettagli=result)
    db.commit()
    return result


@router.post("/jobs/{job_id}/pdf/generate-all")
def generate_pdf_all(job_id: int, payload: PdfGenerateRequest = Body(default=PdfGenerateRequest()), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    settings = get_settings()
    output_dir = Path(payload.output_dir.strip()) if payload.output_dir and payload.output_dir.strip() else Path(settings.output_dir) / f"job_{job_id}"
    report = generate_all_pdfs(db, job, output_dir)
    report["output_dir"] = str(output_dir)
    log_event(db, "pdf_bulk_generated", "Generazione PDF massiva completata", lavoro_id=job_id, dettagli=report)
    db.commit()
    return report


@router.get("/jobs/{job_id}/pdf")
def list_generated_pdfs(job_id: int, db: Session = Depends(get_db)):
    _job_or_404(db, job_id)
    rows = db.query(PdfGenerato).filter(PdfGenerato.lavoro_id == job_id).order_by(PdfGenerato.created_at.desc()).all()
    return [
        {"id": row.id, "file_mtr_id": row.file_mtr_id, "verifica_id": row.verifica_id, "percorso_pdf": row.percorso_pdf, "nome_pdf": row.nome_pdf, "template_pdf": row.template_pdf, "created_at": row.created_at, "esito": row.esito, "errore": row.errore}
        for row in rows
    ]


@router.post("/jobs/{job_id}/registry/sync")
def sync_registry_from_job(job_id: int, db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id)
    report = sync_job_registry(db, job)
    log_event(db, "registry_synced", "Archivio apparecchiature aggiornato dal lavoro VSE", lavoro_id=job_id, dettagli=report)
    db.commit()
    return report


@router.get("/registry/equipment")
def list_registry_equipment(cliente: str | None = None, due_before: str | None = None, db: Session = Depends(get_db)):
    query = db.query(RegistroApparecchiatura)
    if cliente:
        query = query.filter(RegistroApparecchiatura.cliente_nome.ilike(f"%{cliente}%"))
    if due_before:
        query = query.filter(RegistroApparecchiatura.data_prossima_verifica <= due_before)
    rows = query.order_by(RegistroApparecchiatura.cliente_nome, RegistroApparecchiatura.data_prossima_verifica.nullslast(), RegistroApparecchiatura.produttore).all()
    return [_registry_dict(row) for row in rows]


@router.get("/registry/clients")
def list_registry_clients(db: Session = Depends(get_db)):
    rows = db.query(RegistroApparecchiatura.cliente_nome).distinct().order_by(RegistroApparecchiatura.cliente_nome).all()
    return [row[0] for row in rows if row[0]]


@router.get("/registry/equipment/{equipment_id}")
def get_registry_equipment(equipment_id: int, db: Session = Depends(get_db)):
    row = db.get(RegistroApparecchiatura, equipment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Apparecchiatura non trovata")
    return _registry_dict(row)


@router.get("/registry/equipment/{equipment_id}/measurements")
def get_registry_equipment_measurements(equipment_id: int, db: Session = Depends(get_db)):
    row = db.get(RegistroApparecchiatura, equipment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Apparecchiatura non trovata")
    return {"equipment": _registry_dict(row), "measurements": _clean_measurements((row.raw_json or {}).get("measurements") or [])}


@router.get("/registry/equipment/{equipment_id}/trend")
def get_registry_equipment_trend(equipment_id: int, db: Session = Depends(get_db)):
    row = db.get(RegistroApparecchiatura, equipment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Apparecchiatura non trovata")
    history = []
    verifications = (
        db.query(VerificaVse)
        .join(FileMtr, VerificaVse.file_mtr_id == FileMtr.id)
        .join(LavoroVse, FileMtr.lavoro_id == LavoroVse.id)
        .filter(LavoroVse.cliente_nome == row.cliente_nome)
        .order_by(VerificaVse.created_at)
        .all()
    )
    for verification in verifications:
        file_mtr = verification.file_mtr
        job = file_mtr.lavoro if file_mtr else None
        if not file_mtr or not job:
            continue
        data = build_final_pdf_data(job, file_mtr, verification)
        identifier = normalize_registry_identifier(_first_value(data.get("serial"), data.get("matricola"), data.get("seriale"), data.get("invGest"), data.get("inventario"), file_mtr.matricola, file_mtr.seriale, file_mtr.inventario))
        if identifier != row.identificativo:
            continue
        date_value = data.get("testDate") or data.get("data_test") or data.get("data_verifica") or verification.data_verifica or verification.created_at.date().isoformat()
        history.append({"date": str(date_value), "measurements": _clean_measurements(data.get("measurements") or [])})
    series: dict[str, list[dict]] = {}
    for item in history:
        for measurement in item["measurements"]:
            numeric = _numeric_measurement_value(measurement.get("value"))
            if numeric is None:
                continue
            name = measurement.get("name") or measurement.get("description") or "Misura"
            series.setdefault(name, []).append({"date": item["date"], "value": numeric, "unit": measurement.get("unit") or ""})
    return {"equipment": _registry_dict(row), "series": [{"name": name, "points": points} for name, points in series.items() if points]}


@router.get("/registry/calendar.ics")
def export_registry_calendar(cliente: str | None = None, db: Session = Depends(get_db)):
    query = db.query(RegistroApparecchiatura).filter(RegistroApparecchiatura.data_prossima_verifica.isnot(None), RegistroApparecchiatura.data_prossima_verifica != "")
    if cliente:
        query = query.filter(RegistroApparecchiatura.cliente_nome.ilike(f"%{cliente}%"))
    content = build_registry_ics(query.order_by(RegistroApparecchiatura.data_prossima_verifica).all())
    return Response(content=content, media_type="text/calendar", headers={"Content-Disposition": 'attachment; filename="scadenze-vse.ics"'})


def database_status(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def dashboard_counts(db: Session) -> dict:
    return {
        "jobs": db.query(func.count(LavoroVse.id)).scalar() or 0,
        "open_anomalies": db.query(func.count(Anomalia.id)).filter(Anomalia.stato == "aperta").scalar() or 0,
    }


def _job_or_404(db: Session, job_id: int) -> LavoroVse:
    job = db.get(LavoroVse, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Lavoro VSE non trovato")
    return job


def _file_or_404(db: Session, file_mtr_id: int, job_id: int | None = None) -> FileMtr:
    file_mtr = db.get(FileMtr, file_mtr_id)
    if not file_mtr or (job_id is not None and file_mtr.lavoro_id != job_id):
        raise HTTPException(status_code=404, detail="File MTR non trovato")
    return file_mtr


def _ensure_verification(db: Session, file_mtr: FileMtr) -> VerificaVse:
    if file_mtr.verifiche:
        return file_mtr.verifiche[0]
    equipment = file_mtr.matched_apparecchiature[0] if file_mtr.matched_apparecchiature else None
    verification = VerificaVse(
        file_mtr_id=file_mtr.id,
        apparecchiatura_id=equipment.id if equipment else None,
        dati_ansur_json=file_mtr.parsed_json or {},
        dati_excel_json=equipment.raw_data if equipment else {},
    )
    db.add(verification)
    db.flush()
    return verification


def _review_summary(db: Session, file_mtr: FileMtr) -> dict:
    verification = _ensure_verification(db, file_mtr)
    return {
        "file_mtr_id": file_mtr.id,
        "nome_file": file_mtr.nome_file,
        "template_ansur": file_mtr.template_ansur,
        "is_permanent_three_measure_template": file_mtr.is_permanent_three_measure_template,
        "stato": file_mtr.stato,
        "stato_revisione": verification.stato_revisione,
        "matricola": file_mtr.matricola,
        "modello": file_mtr.modello,
    }


def _equipment_dict(row: Apparecchiatura) -> dict:
    data = {field: getattr(row, field) for field in ("id", "row_index", "matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto", "raw_data")}
    verification = row.verifiche[0] if row.verifiche else None
    data["esito"] = verification.esito_excel if verification else None
    data["data_verifica"] = verification.data_verifica if verification else None
    return data


def _anomaly_dict(row: Anomalia) -> dict:
    return {
        "id": row.id,
        "lavoro_id": row.lavoro_id,
        "lavoro_titolo": row.lavoro.titolo if row.lavoro else "",
        "cliente_nome": row.lavoro.cliente_nome if row.lavoro else "",
        "tipo": row.tipo,
        "severita": row.severita,
        "messaggio": row.messaggio,
        "stato": row.stato,
        "riferimenti": row.riferimenti,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _mtr_dict(row: FileMtr) -> dict:
    return {field: getattr(row, field) for field in ("id", "path_corrente", "nome_file", "matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto", "parsed_data", "stato", "source_type", "template_ansur", "is_permanent_three_measure_template", "parsed_json", "measurement_index_json")}


def _verification_dict(row: VerificaVse) -> dict:
    fields = (
        "id", "apparecchiatura_id", "file_mtr_id", "esito_excel", "esito_mtr", "data_verifica", "differenze", "tecnico", "firma_path", "proprieta",
        "periodicita", "tensione", "frequenza", "potenza", "potenza_unita", "protezione", "installazione", "mobilita", "classe_elettrica",
        "parte_applicata", "controlli_visivi_json", "controlli_funzionali_json", "note", "stato_revisione", "campi_bloccati_json",
        "dati_revisionati_json", "dati_ansur_json", "dati_excel_json", "dati_finali_pdf_json",
    )
    return {field: getattr(row, field) for field in fields}


def _field_badges(verification: VerificaVse, final: dict) -> dict:
    badges = {}
    revised = verification.dati_revisionati_json or {}
    excel = verification.dati_excel_json or {}
    ansur = source_data(verification.dati_ansur_json or {})
    for field in final:
        if field in revised:
            badges[field] = "modificato manualmente"
        elif field in excel:
            badges[field] = "derivato da Excel"
        elif field in ansur and ansur.get(field):
            badges[field] = "derivato da MTR"
        else:
            badges[field] = "default lavoro"
    return badges


def _registry_dict(row: RegistroApparecchiatura) -> dict:
    return {
        "id": row.id,
        "cliente_nome": row.cliente_nome,
        "presidio": row.presidio,
        "reparto": row.reparto,
        "stanza": row.stanza,
        "ubicazione": row.ubicazione,
        "tipologia": row.tipologia,
        "produttore": row.produttore,
        "modello": row.modello,
        "matricola": row.matricola,
        "seriale": row.seriale,
        "inventario_gestionale": row.inventario_gestionale,
        "inventario_ente": row.inventario_ente,
        "civab": row.civab,
        "identificativo": row.identificativo,
        "data_ultima_verifica": row.data_ultima_verifica,
        "periodicita_mesi": row.periodicita_mesi,
        "data_prossima_verifica": row.data_prossima_verifica,
        "esito_ultima_verifica": row.esito_ultima_verifica,
        "tecnico_ultima_verifica": row.tecnico_ultima_verifica,
        "ultimo_lavoro_id": row.ultimo_lavoro_id,
        "ultimo_file_mtr_id": row.ultimo_file_mtr_id,
        "ultima_verifica_id": row.ultima_verifica_id,
        "calendar_event_id": row.calendar_event_id,
        "has_measurements": bool((row.raw_json or {}).get("measurements")),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _folder_roots() -> list[dict[str, str]]:
    roots = []
    if hasattr(Path, "home"):
        home = Path.home()
        roots.append({"name": f"Home ({home})", "path": str(home)})
    for code in range(ord("A"), ord("Z") + 1):
        drive = Path(f"{chr(code)}:\\")
        if drive.exists():
            roots.append({"name": str(drive), "path": str(drive)})
    return roots


def _clean_measurements(measurements: list[dict]) -> list[dict]:
    cleaned = []
    for item in measurements:
        value = item.get("value") or item.get("valore") or ""
        text = str(value).strip()
        if not text or "scelta" in text.lower():
            continue
        cleaned.append(
            {
                "name": item.get("name") or item.get("nome") or item.get("description") or item.get("descrizione") or "Misura",
                "description": item.get("description") or item.get("descrizione") or "",
                "value": text,
                "unit": item.get("unit") or item.get("unita") or "",
                "status": item.get("status") or item.get("result") or item.get("esito") or "",
            }
        )
    return cleaned


def _numeric_measurement_value(value: object) -> float | None:
    text_value = str(value or "").replace(",", ".")
    if not text_value.strip() or "scelta" in text_value.lower():
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text_value)
    return float(match.group(0)) if match else None


def _first_value(*values: object) -> str:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return ""
