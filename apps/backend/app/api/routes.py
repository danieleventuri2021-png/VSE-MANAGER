from pathlib import Path
import shutil
import zipfile
from datetime import datetime
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Anomalia, Apparecchiatura, FileMtr, LavoroVse, LogOperativo, PdfGenerato, RegistroApparecchiatura, Utente, VerificaVse
from app.schemas.jobs import ApplyResult, FolderRequest, JobCreate, JobRead, PdfGenerateRequest, SystemPorts
from app.services.anomaly_service import create_anomaly
from app.services.backup_service import create_backup
from app.services.bulk_pdf_service import build_final_pdf_data, generate_all_pdfs, generate_one_pdf
from app.services.equipment_registry_service import build_registry_ics, sync_job_registry
from app.services.equipment_registry_service import normalize_identifier as normalize_registry_identifier
from app.services.equipment_registry_service import registry_data_from_pdf_data, registry_match_score
from app.services.difference_analyzer import analyze_differences
from app.services.excel_importer import import_excel
from app.services.file_renamer import rename_mtr
from app.services.log_service import log_event
from app.services.matcher import match_records
from app.services.mtr_parser import parse_mtr_file, scan_mtr_folder
from app.services.mtr_writer import write_mtr_updates
from app.services.port_checker import check_ports
from app.services.session_defaults_service import apply_defaults_to_verification, update_job_defaults
from app.services.auth_service import authenticate_user, create_access_token, get_current_user, hash_password, verify_password
from app.services.source_writer import save_to_source
from app.services.vse_defaults import ansur_defaults, job_defaults, source_data

router = APIRouter()
auth_router = APIRouter()

EQUIPMENT_FIELDS = ("row_index", "matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto", "raw_data")


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    nome: str | None = None
    ruolo: str = "operatore"


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class UserUpdateRequest(BaseModel):
    username: str | None = None
    nome: str | None = None
    ruolo: str | None = None
    attivo: bool | None = None
    password: str | None = None


class MatchFieldResolution(BaseModel):
    field: str
    direction: str


class MatchResolveRequest(BaseModel):
    equipment_id: int
    file_mtr_id: int
    fields: list[MatchFieldResolution]


class BulkDeleteRequest(BaseModel):
    ids: list[int]
    confirm: str


@auth_router.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username.strip(), payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Username o password non validi")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": _user_dict(user)}


@auth_router.get("/auth/me")
def me(user: Utente = Depends(get_current_user)):
    return _user_dict(user)


@auth_router.get("/auth/users")
def list_users(current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    return [_user_dict(user) for user in db.query(Utente).order_by(Utente.username).all()]


@auth_router.post("/auth/users")
def create_user(payload: UserCreateRequest, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    username = payload.username.strip()
    if len(username) < 3 or len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Utente minimo 3 caratteri e password minimo 6 caratteri")
    existing = db.query(Utente).filter(Utente.username == username).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Utente gia esistente")
    user = Utente(username=username, password_hash=hash_password(payload.password), nome=payload.nome, ruolo=payload.ruolo or "operatore", attivo=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_dict(user)


@auth_router.put("/auth/users/{user_id}")
def update_user(user_id: int, payload: UserUpdateRequest, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    user = db.get(Utente, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    username = payload.username.strip() if payload.username is not None else user.username
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username minimo 3 caratteri")
    existing = db.query(Utente).filter(Utente.username == username, Utente.id != user_id).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Username gia utilizzato")
    if user.username == "admin" and username != "admin":
        raise HTTPException(status_code=400, detail="L'utente admin non puo essere rinominato")

    if payload.attivo is False and (user.username == "admin" or user.id == current_user.id):
        raise HTTPException(status_code=400, detail="Non puoi disabilitare questo utente")
    if payload.ruolo and payload.ruolo not in {"admin", "operatore"}:
        raise HTTPException(status_code=400, detail="Ruolo non valido")
    if payload.ruolo and user.username == "admin" and payload.ruolo != "admin":
        raise HTTPException(status_code=400, detail="L'utente admin deve restare amministratore")
    if payload.password is not None and payload.password and len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password minimo 6 caratteri")

    user.username = username
    if payload.nome is not None:
        user.nome = payload.nome.strip() or None
    if payload.ruolo:
        user.ruolo = payload.ruolo
    if payload.attivo is not None:
        user.attivo = payload.attivo
    if payload.password:
        user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return _user_dict(user)


@auth_router.delete("/auth/users/{user_id}")
def delete_user(user_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_admin(current_user)
    user = db.get(Utente, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="L'utente admin non puo essere cancellato")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Non puoi cancellare l'utente in uso")
    db.delete(user)
    db.commit()
    return {"deleted": user_id}


@auth_router.post("/auth/change-password")
def change_password(payload: PasswordChangeRequest, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="La nuova password deve avere almeno 6 caratteri")
    user = db.get(Utente, current_user.id)
    if not user or not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Password attuale non valida")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"changed": True}


@router.get("/system/ports", response_model=SystemPorts)
def system_ports():
    settings = get_settings()
    return check_ports(settings.backend_port, _origin_port(settings.frontend_origin))


@router.get("/dashboard/status")
def dashboard_status(current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    return dashboard_counts(db, current_user)


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
def create_job(payload: JobCreate, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = LavoroVse(titolo=payload.titolo, cliente_nome=payload.cliente_nome, mtr_folder=payload.mtr_folder, owner_user_id=current_user.id)
    db.add(job)
    db.flush()
    log_event(db, "job_created", f"Lavoro creato: {payload.titolo}", lavoro_id=job.id)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    return _jobs_query(db, current_user).order_by(LavoroVse.created_at.desc()).all()


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    return _job_or_404(db, job_id, current_user)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int, confirm: str, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    expected = f"ELIMINA LAVORO {job.id}"
    if confirm != expected:
        raise HTTPException(status_code=400, detail=f"Conferma non valida. Digitare: {expected}")
    _delete_job_pdf_files(job)
    title = job.titolo
    db.delete(job)
    db.commit()
    return {"deleted": job_id, "title": title}


@router.post("/jobs/{job_id}/excel", response_model=JobRead)
def upload_excel(job_id: int, file: UploadFile = File(...), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
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


@router.post("/jobs/{job_id}/asset", response_model=JobRead)
def upload_job_asset(job_id: int, field: str, file: UploadFile = File(...), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    target_field = {
        "firma_path": "firma_default_path",
        "template_pdf": "template_pdf",
        "intestazione_pdf": "intestazione_pdf",
    }.get(field)
    if not target_field:
        raise HTTPException(status_code=400, detail="Campo file non valido")
    filename = Path(file.filename or "file").name
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Nome file non valido")
    settings = get_settings()
    target_dir = Path(settings.template_dir) / f"job_{job_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    setattr(job, target_field, str(target))
    log_event(db, "job_asset_uploaded", f"File impostazioni lavoro caricato: {filename}", lavoro_id=job_id, dettagli={"field": field, "path": str(target)})
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/mtr-folder", response_model=JobRead)
def import_mtr_folder(job_id: int, payload: FolderRequest, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    parsed_files = scan_mtr_folder(payload.folder_path)
    _replace_mtr_files(db, job, parsed_files, payload.folder_path)
    log_event(db, "mtr_imported", f"Importati {len(parsed_files)} file MTR/CSV", lavoro_id=job_id)
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/mtr-upload", response_model=JobRead)
def upload_mtr_files(job_id: int, files: list[UploadFile] = File(...), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    if not files:
        raise HTTPException(status_code=400, detail="Nessun file MTR/CSV selezionato")

    settings = get_settings()
    target_dir = Path(settings.input_dir) / f"job_{job_id}" / "mtr_upload"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    for upload in files:
        filename = Path(upload.filename or "").name
        if not filename:
            continue
        suffix = Path(filename).suffix.lower()
        if suffix == ".zip":
            zip_path = target_dir / filename
            with zip_path.open("wb") as handle:
                shutil.copyfileobj(upload.file, handle)
            saved_paths.extend(_extract_mtr_zip(zip_path, target_dir / "zip"))
        elif suffix in {".mtr", ".csv"}:
            target = _unique_path(target_dir, filename)
            with target.open("wb") as handle:
                shutil.copyfileobj(upload.file, handle)
            saved_paths.append(target)
        else:
            raise HTTPException(status_code=400, detail=f"Formato file non supportato: {filename}")

    if not saved_paths:
        raise HTTPException(status_code=400, detail="Nessun file MTR/CSV valido trovato")

    parsed_files = [parse_mtr_file(path) for path in sorted(saved_paths, key=lambda item: item.name.lower())]
    _replace_mtr_files(db, job, parsed_files, str(target_dir))
    log_event(db, "mtr_uploaded", f"Caricati {len(parsed_files)} file MTR/CSV", lavoro_id=job_id, dettagli={"files": [path.name for path in saved_paths]})
    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/analyze", response_model=JobRead)
def analyze_job(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
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
                create_anomaly(db, job_id, "differenza_excel_mtr", "Differenze tra Excel e MTR/CSV", "warning", {"equipment_id": eq.id, "mtr_id": mtr.id, "fields": differences["fields"]})
        else:
            eq.matched_file_mtr_id = None
            create_anomaly(db, job_id, "mtr_mancante", "Nessun file MTR/CSV associato alla riga Excel", "error", {"equipment_id": eq.id, "score": match.score})
        counts[match.status] += 1
    for index in orphans:
        mtr_rows[index].stato = "mtr_orfano"
        create_anomaly(db, job_id, "mtr_orfano", "File MTR/CSV non associato ad alcuna riga Excel", "info", {"mtr_id": mtr_rows[index].id})
    job.stato = "analizzato"
    job.summary = {**job.summary, **counts}
    log_event(db, "job_analyzed", "Analisi completata", lavoro_id=job_id, dettagli=counts)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}/matches")
def get_matches(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    rows = db.query(Apparecchiatura).filter(Apparecchiatura.lavoro_id == job_id).order_by(Apparecchiatura.row_index).all()
    matches = [
        {
            "equipment": _equipment_dict(row),
            "status": row.match_status,
            "score": row.match_score,
            "mtr": _mtr_dict(row.matched_file_mtr) if row.matched_file_mtr else None,
            "reason": _match_reason(_equipment_dict(row), _mtr_dict(row.matched_file_mtr) if row.matched_file_mtr else None),
            "differences": analyze_differences(_equipment_dict(row), _mtr_dict(row.matched_file_mtr) if row.matched_file_mtr else None),
            "registry_match": _registry_candidate_for_match(db, job, row.matched_file_mtr, row.verifiche[0] if row.verifiche else None),
        }
        for row in rows
    ]
    orphan_mtrs = (
        db.query(FileMtr)
        .filter(FileMtr.lavoro_id == job_id, ~FileMtr.matched_apparecchiature.any())
        .order_by(FileMtr.id)
        .all()
    )
    matches.extend(
        {
            "equipment": None,
            "status": file_mtr.stato or "mtr_orfano",
            "score": None,
            "mtr": _mtr_dict(file_mtr),
            "reason": "File MTR/CSV senza riga Excel associata",
            "differences": {"missing_excel": True, "fields": []},
            "registry_match": _registry_candidate_for_match(db, job, file_mtr, file_mtr.verifiche[0] if file_mtr.verifiche else None),
        }
        for file_mtr in orphan_mtrs
    )
    return matches


@router.post("/jobs/{job_id}/matches/resolve")
def resolve_match_differences(job_id: int, payload: MatchResolveRequest, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    job = _job_or_404(db, job_id, current_user)
    equipment = db.get(Apparecchiatura, payload.equipment_id)
    file_mtr = db.get(FileMtr, payload.file_mtr_id)
    if not equipment or equipment.lavoro_id != job.id:
        raise HTTPException(status_code=404, detail="Riga Excel non trovata")
    if not file_mtr or file_mtr.lavoro_id != job.id:
        raise HTTPException(status_code=404, detail="File MTR/CSV non trovato")
    allowed_fields = {"matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto", "stanza"}
    mtr_updates = {}
    excel_updates = {}
    for item in payload.fields:
        if item.field not in allowed_fields:
            raise HTTPException(status_code=400, detail=f"Campo non aggiornabile: {item.field}")
        if item.direction == "mtr_from_excel":
            value = _equipment_field_value(equipment, item.field)
            mtr_updates[item.field] = value
        elif item.direction == "excel_from_mtr":
            value = _mtr_field_value(file_mtr, item.field)
            excel_updates[item.field] = value
        else:
            raise HTTPException(status_code=400, detail=f"Direzione non valida: {item.direction}")
    source_result = None
    if mtr_updates:
        source_result = save_to_source(file_mtr.path_corrente, mtr_updates, settings.backup_dir)
        parsed = source_result["parsed"]
        _update_file_mtr_from_parsed(file_mtr, parsed)
    if excel_updates:
        raw_data = dict(equipment.raw_data or {})
        for field, value in excel_updates.items():
            if hasattr(equipment, field):
                setattr(equipment, field, value)
            raw_data[field] = value
        equipment.raw_data = raw_data
    verification = _ensure_verification(db, file_mtr)
    equipment.matched_file_mtr_id = file_mtr.id
    verification.apparecchiatura_id = equipment.id
    verification.dati_ansur_json = file_mtr.parsed_json or {}
    verification.dati_excel_json = equipment.raw_data or {}
    differences = analyze_differences(_equipment_dict(equipment), _mtr_dict(file_mtr))
    if not differences["fields"]:
        equipment.match_status = "certo"
        file_mtr.stato = "abbinato"
    log_event(db, "match_resolved", "Differenze abbinamento risolte", lavoro_id=job_id, dettagli={"equipment_id": equipment.id, "file_mtr_id": file_mtr.id, "mtr_fields": list(mtr_updates), "excel_fields": list(excel_updates), "source_backup": source_result.get("backup") if source_result else None})
    db.commit()
    db.refresh(equipment)
    db.refresh(file_mtr)
    return {
        "equipment": _equipment_dict(equipment),
        "mtr": _mtr_dict(file_mtr),
        "status": equipment.match_status,
        "score": equipment.match_score,
        "reason": _match_reason(_equipment_dict(equipment), _mtr_dict(file_mtr)),
        "differences": analyze_differences(_equipment_dict(equipment), _mtr_dict(file_mtr)),
    }


@router.get("/jobs/{job_id}/anomalies")
def get_anomalies(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _job_or_404(db, job_id, current_user)
    return db.query(Anomalia).filter(Anomalia.lavoro_id == job_id).order_by(Anomalia.created_at.desc()).all()


@router.get("/anomalies")
def list_all_anomalies(stato: str | None = "aperta", current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    query = (
        db.query(Anomalia)
        .options(joinedload(Anomalia.lavoro))
        .join(LavoroVse, Anomalia.lavoro_id == LavoroVse.id)
    )
    if not _is_admin(current_user):
        query = query.filter(LavoroVse.owner_user_id == current_user.id)
    if stato:
        query = query.filter(Anomalia.stato == stato)
    rows = query.order_by(LavoroVse.titolo, Anomalia.created_at.desc()).all()
    return [_anomaly_dict(row) for row in rows]


@router.delete("/anomalies/{anomaly_id}")
def delete_anomaly(anomaly_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(Anomalia, anomaly_id)
    if not row or not _can_access_job(row.lavoro, current_user):
        raise HTTPException(status_code=404, detail="Anomalia non trovata")
    db.delete(row)
    db.commit()
    return {"deleted": anomaly_id}


@router.delete("/anomalies")
def delete_all_anomalies(stato: str | None = "aperta", current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Anomalia)
    if not _is_admin(current_user):
        query = query.join(LavoroVse, Anomalia.lavoro_id == LavoroVse.id).filter(LavoroVse.owner_user_id == current_user.id)
    if stato:
        query = query.filter(Anomalia.stato == stato)
    rows = query.all()
    deleted = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return {"deleted": deleted}


@router.post("/jobs/{job_id}/apply", response_model=ApplyResult)
def apply_job(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
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
    log_event(db, "changes_applied", "Aggiornamenti MTR/CSV applicati", lavoro_id=job_id, dettagli={"backup_dir": str(backup_dir), "renamed": len(renamed)})
    db.commit()
    return ApplyResult(backup_dir=str(backup_dir), renamed=renamed, conflicts=conflicts)


@router.get("/jobs/{job_id}/logs")
def get_logs(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _job_or_404(db, job_id, current_user)
    return db.query(LogOperativo).filter(LogOperativo.lavoro_id == job_id).order_by(LogOperativo.created_at.desc()).all()


@router.put("/jobs/{job_id}/settings", response_model=JobRead)
def update_job_settings(job_id: int, payload: dict = Body(...), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    update_job_defaults(job, payload)
    log_event(db, "job_defaults_updated", "Default lavoro aggiornati", lavoro_id=job_id, dettagli=payload)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs/{job_id}/review")
def get_review_list(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _job_or_404(db, job_id, current_user)
    files = db.query(FileMtr).filter(FileMtr.lavoro_id == job_id).order_by(FileMtr.id).all()
    return [_review_summary(db, file_mtr) for file_mtr in files]


@router.get("/jobs/{job_id}/review/{file_mtr_id}")
def get_review_detail(job_id: int, file_mtr_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    file_mtr = _file_or_404(db, file_mtr_id, job_id, current_user)
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
def save_review_detail(job_id: int, file_mtr_id: int, payload: dict = Body(...), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    file_mtr = _file_or_404(db, file_mtr_id, job_id, current_user)
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
def apply_job_defaults(job_id: int, payload: dict = Body(default={}), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    if payload.get("save_as_job_default"):
        update_job_defaults(job, payload.get("values") or {})
    changed = []
    file_mtrs = (
        db.query(FileMtr)
        .options(selectinload(FileMtr.verifiche), selectinload(FileMtr.matched_apparecchiature))
        .filter(FileMtr.lavoro_id == job_id)
        .all()
    )
    for file_mtr in file_mtrs:
        verification = _ensure_verification(db, file_mtr)
        fields = apply_defaults_to_verification(job, verification, payload.get("values") or {})
        if fields:
            verification.dati_finali_pdf_json = build_final_pdf_data(job, file_mtr, verification)
            changed.append({"file_mtr_id": file_mtr.id, "fields": fields})
    log_event(db, "job_defaults_applied", "Default lavoro applicati agli MTR/CSV non bloccati", lavoro_id=job_id, dettagli={"changed": len(changed)})
    db.commit()
    return {"updated": len(changed), "items": changed}


@router.post("/files/{file_mtr_id}/save-source")
def save_source(file_mtr_id: int, payload: dict = Body(default={}), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    file_mtr = db.get(FileMtr, file_mtr_id)
    if not file_mtr or not _can_access_job(file_mtr.lavoro, current_user):
        raise HTTPException(status_code=404, detail="File MTR/CSV non trovato")
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
def generate_pdf_one(job_id: int, file_mtr_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    file_mtr = _file_or_404(db, file_mtr_id, job_id, current_user)
    settings = get_settings()
    result = generate_one_pdf(db, job, file_mtr, Path(settings.output_dir) / f"job_{job_id}")
    log_event(db, "pdf_generated", f"PDF generato: {result['filename']}", lavoro_id=job_id, dettagli=result)
    db.commit()
    return result


@router.post("/jobs/{job_id}/pdf/generate-all")
def generate_pdf_all(job_id: int, payload: PdfGenerateRequest = Body(default=PdfGenerateRequest()), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    settings = get_settings()
    output_dir = Path(payload.output_dir.strip()) if payload.output_dir and payload.output_dir.strip() else Path(settings.output_dir) / f"job_{job_id}"
    report = generate_all_pdfs(db, job, output_dir)
    report["output_dir"] = str(output_dir)
    log_event(db, "pdf_bulk_generated", "Generazione PDF massiva completata", lavoro_id=job_id, dettagli=report)
    db.commit()
    return report


@router.get("/jobs/{job_id}/pdf")
def list_generated_pdfs(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _job_or_404(db, job_id, current_user)
    rows = db.query(PdfGenerato).filter(PdfGenerato.lavoro_id == job_id).order_by(PdfGenerato.created_at.desc()).all()
    return [
        {"id": row.id, "file_mtr_id": row.file_mtr_id, "verifica_id": row.verifica_id, "percorso_pdf": row.percorso_pdf, "nome_pdf": row.nome_pdf, "template_pdf": row.template_pdf, "created_at": row.created_at, "esito": row.esito, "errore": row.errore}
        for row in rows
    ]


@router.get("/jobs/{job_id}/pdf/{pdf_id}/download")
def download_generated_pdf(job_id: int, pdf_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _job_or_404(db, job_id, current_user)
    row = db.query(PdfGenerato).filter(PdfGenerato.id == pdf_id, PdfGenerato.lavoro_id == job_id).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="PDF non trovato")
    path = Path(row.percorso_pdf)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File PDF non presente sul server")
    return FileResponse(path, media_type="application/pdf", filename=row.nome_pdf or path.name)


@router.get("/jobs/{job_id}/pdf/download-all")
def download_all_generated_pdfs(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    _job_or_404(db, job_id, current_user)
    rows = db.query(PdfGenerato).filter(PdfGenerato.lavoro_id == job_id, PdfGenerato.esito == "generato").order_by(PdfGenerato.created_at.desc()).all()
    existing = [row for row in rows if row.percorso_pdf and Path(row.percorso_pdf).exists()]
    if not existing:
        raise HTTPException(status_code=404, detail="Nessun PDF disponibile per il download")

    settings = get_settings()
    export_dir = Path(settings.output_dir) / f"job_{job_id}"
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_path = export_dir / f"pdf_lavoro_{job_id}.zip"
    used_names: set[str] = set()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in existing:
            source = Path(row.percorso_pdf)
            arcname = _unique_archive_name(row.nome_pdf or source.name, used_names)
            archive.write(source, arcname=arcname)
    return FileResponse(zip_path, media_type="application/zip", filename=zip_path.name)


@router.post("/jobs/{job_id}/registry/sync")
def sync_registry_from_job(job_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _job_or_404(db, job_id, current_user)
    report = sync_job_registry(db, job)
    log_event(db, "registry_synced", "Archivio apparecchiature aggiornato dal lavoro VSE", lavoro_id=job_id, dettagli=report)
    db.commit()
    return report


@router.get("/registry/equipment")
def list_registry_equipment(cliente: str | None = None, due_before: str | None = None, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    query = _registry_query(db, current_user)
    if cliente:
        query = query.filter(RegistroApparecchiatura.cliente_nome.ilike(f"%{cliente}%"))
    if due_before:
        query = query.filter(RegistroApparecchiatura.data_prossima_verifica <= due_before)
    rows = query.order_by(RegistroApparecchiatura.cliente_nome, RegistroApparecchiatura.data_prossima_verifica.nullslast(), RegistroApparecchiatura.produttore).all()
    return [_registry_dict(row) for row in rows]


@router.get("/registry/clients")
def list_registry_clients(current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = _registry_query(db, current_user).with_entities(RegistroApparecchiatura.cliente_nome).distinct().order_by(RegistroApparecchiatura.cliente_nome).all()
    return [row[0] for row in rows if row[0]]


@router.get("/registry/equipment/{equipment_id}")
def get_registry_equipment(equipment_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(RegistroApparecchiatura, equipment_id)
    if not row or not _can_access_registry(row, current_user):
        raise HTTPException(status_code=404, detail="Apparecchiatura non trovata")
    return _registry_dict(row)


@router.delete("/registry/equipment")
def delete_registry_equipment(payload: BulkDeleteRequest = Body(...), current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = sorted({int(item) for item in payload.ids if int(item) > 0})
    if not ids:
        raise HTTPException(status_code=400, detail="Nessuna apparecchiatura selezionata")
    expected = f"ELIMINA {len(ids)} ARCHIVIO"
    if payload.confirm != expected:
        raise HTTPException(status_code=400, detail=f"Conferma non valida. Digitare: {expected}")
    rows = db.query(RegistroApparecchiatura).filter(RegistroApparecchiatura.id.in_(ids)).all()
    allowed = [row for row in rows if _can_access_registry(row, current_user)]
    if len(allowed) != len(ids):
        raise HTTPException(status_code=404, detail="Una o piu apparecchiature non sono accessibili")
    summary = [{"id": row.id, "cliente_nome": row.cliente_nome, "identificativo": row.identificativo} for row in allowed]
    for row in allowed:
        db.delete(row)
    db.commit()
    return {"deleted": len(allowed), "items": summary}


@router.get("/registry/equipment/{equipment_id}/measurements")
def get_registry_equipment_measurements(equipment_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(RegistroApparecchiatura, equipment_id)
    if not row or not _can_access_registry(row, current_user):
        raise HTTPException(status_code=404, detail="Apparecchiatura non trovata")
    return {"equipment": _registry_dict(row), "measurements": _clean_measurements((row.raw_json or {}).get("measurements") or [])}


@router.get("/registry/equipment/{equipment_id}/trend")
def get_registry_equipment_trend(equipment_id: int, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(RegistroApparecchiatura, equipment_id)
    if not row or not _can_access_registry(row, current_user):
        raise HTTPException(status_code=404, detail="Apparecchiatura non trovata")
    history = []
    verifications = (
        db.query(VerificaVse)
        .options(joinedload(VerificaVse.file_mtr).joinedload(FileMtr.lavoro))
        .join(FileMtr, VerificaVse.file_mtr_id == FileMtr.id)
        .join(LavoroVse, FileMtr.lavoro_id == LavoroVse.id)
        .filter(LavoroVse.cliente_nome == row.cliente_nome, LavoroVse.owner_user_id == row.owner_user_id)
        .order_by(VerificaVse.created_at)
        .all()
    )
    for verification in verifications:
        file_mtr = verification.file_mtr
        job = file_mtr.lavoro if file_mtr else None
        if not file_mtr or not job:
            continue
        data = build_final_pdf_data(job, file_mtr, verification)
        row_data = registry_data_from_pdf_data(job, file_mtr, verification, data)
        if registry_match_score(row, row_data)["score"] < 90:
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
def export_registry_calendar(cliente: str | None = None, current_user: Utente = Depends(get_current_user), db: Session = Depends(get_db)):
    query = _registry_query(db, current_user).filter(RegistroApparecchiatura.data_prossima_verifica.isnot(None), RegistroApparecchiatura.data_prossima_verifica != "")
    if cliente:
        query = query.filter(RegistroApparecchiatura.cliente_nome.ilike(f"%{cliente}%"))
    content = build_registry_ics(query.order_by(RegistroApparecchiatura.data_prossima_verifica).all())
    return Response(content=content, media_type="text/calendar", headers={"Content-Disposition": 'attachment; filename="scadenze-vse.ics"'})


def _replace_mtr_files(db: Session, job: LavoroVse, parsed_files: list[dict], folder_path: str) -> None:
    db.query(FileMtr).filter(FileMtr.lavoro_id == job.id).delete()
    for parsed in parsed_files:
        db.add(
            FileMtr(
                lavoro_id=job.id,
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
    job.mtr_folder = folder_path
    job.stato = "mtr_importati"
    job.summary = {**(job.summary or {}), "mtr_files": len(parsed_files)}


def _update_file_mtr_from_parsed(row: FileMtr, parsed: dict) -> None:
    row.parsed_data = parsed
    row.parsed_json = parsed.get("normalized") or {}
    row.measurement_index_json = parsed.get("measurement_index") or {}
    row.matricola = parsed.get("matricola")
    row.seriale = parsed.get("seriale")
    row.inventario = parsed.get("inventario")
    row.produttore = parsed.get("produttore")
    row.modello = parsed.get("modello")
    row.descrizione = parsed.get("descrizione")
    row.reparto = parsed.get("reparto")
    row.esito = parsed.get("esito")
    row.template_ansur = parsed.get("template_ansur")
    row.is_permanent_three_measure_template = bool(parsed.get("is_permanent_three_measure_template"))
    row.source_type = (parsed.get("normalized") or {}).get("source_type", row.source_type)
    row.last_source_write_at = datetime.utcnow()


def _extract_mtr_zip(zip_path: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                filename = Path(info.filename).name
                if not filename or Path(filename).suffix.lower() not in {".mtr", ".csv"}:
                    continue
                target = _unique_path(output_dir, filename)
                with archive.open(info) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
                extracted.append(target)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail=f"Archivio ZIP non valido: {zip_path.name}")
    return extracted


def _unique_path(folder: Path, filename: str) -> Path:
    safe_name = Path(filename).name
    target = folder / safe_name
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 2
    while True:
        candidate = folder / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _unique_archive_name(filename: str, used_names: set[str]) -> str:
    safe_name = Path(filename).name or "documento.pdf"
    if safe_name not in used_names:
        used_names.add(safe_name)
        return safe_name
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix or ".pdf"
    counter = 2
    while True:
        candidate = f"{stem}_{counter}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        counter += 1


def _origin_port(origin: str) -> int:
    parsed = urlparse(origin)
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    return 80


def database_status(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def dashboard_counts(db: Session, user: Utente | None = None) -> dict:
    jobs_query = db.query(func.count(LavoroVse.id))
    anomalies_query = db.query(func.count(Anomalia.id)).join(LavoroVse, Anomalia.lavoro_id == LavoroVse.id).filter(Anomalia.stato == "aperta")
    if user is not None and not _is_admin(user):
        jobs_query = jobs_query.filter(LavoroVse.owner_user_id == user.id)
        anomalies_query = anomalies_query.filter(LavoroVse.owner_user_id == user.id)
    return {
        "jobs": jobs_query.scalar() or 0,
        "open_anomalies": anomalies_query.scalar() or 0,
    }


def _jobs_query(db: Session, user: Utente):
    query = db.query(LavoroVse)
    if not _is_admin(user):
        query = query.filter(LavoroVse.owner_user_id == user.id)
    return query


def _registry_query(db: Session, user: Utente):
    query = db.query(RegistroApparecchiatura)
    if not _is_admin(user):
        query = query.filter(RegistroApparecchiatura.owner_user_id == user.id)
    return query


def _job_or_404(db: Session, job_id: int, user: Utente) -> LavoroVse:
    job = _jobs_query(db, user).filter(LavoroVse.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Lavoro VSE non trovato")
    return job


def _file_or_404(db: Session, file_mtr_id: int, job_id: int | None = None, user: Utente | None = None) -> FileMtr:
    file_mtr = db.get(FileMtr, file_mtr_id)
    if not file_mtr or (job_id is not None and file_mtr.lavoro_id != job_id) or (user is not None and not _can_access_job(file_mtr.lavoro, user)):
        raise HTTPException(status_code=404, detail="File MTR/CSV non trovato")
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
    raw = row.raw_data or {}
    data["stanza"] = raw.get("stanza") or raw.get("STANZA") or raw.get("Location") or raw.get("LOCATION") or raw.get("ubicazione")
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
    data = {field: getattr(row, field) for field in ("id", "path_corrente", "nome_file", "matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto", "parsed_data", "stato", "source_type", "template_ansur", "is_permanent_three_measure_template", "parsed_json", "measurement_index_json")}
    data["stanza"] = ((row.parsed_json or {}).get("dut") or {}).get("location") or row.reparto
    return data


def _equipment_field_value(row: Apparecchiatura, field: str) -> object:
    if hasattr(row, field):
        return getattr(row, field)
    raw = row.raw_data or {}
    return raw.get(field) or raw.get(field.upper()) or raw.get(field.capitalize())


def _mtr_field_value(row: FileMtr, field: str) -> object:
    if field == "stanza":
        return ((row.parsed_json or {}).get("dut") or {}).get("location") or row.reparto
    if hasattr(row, field):
        return getattr(row, field)
    return None


def _match_reason(equipment: dict, mtr: dict | None) -> str:
    if not mtr:
        return "Nessun file MTR/CSV compatibile trovato"
    if _same_value(equipment.get("matricola"), mtr.get("matricola")) or _same_value(equipment.get("seriale"), mtr.get("seriale")):
        return "Matricola/seriale uguale"
    if _same_value(equipment.get("inventario"), mtr.get("inventario")):
        return "Inventario uguale"
    return "Corrispondenza stimata da produttore, modello, descrizione o inventario"


def _same_value(left: object, right: object) -> bool:
    return bool(left and right and re.sub(r"[^a-zA-Z0-9]+", "", str(left)).upper() == re.sub(r"[^a-zA-Z0-9]+", "", str(right)).upper())


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
            badges[field] = "derivato da MTR/CSV"
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


def _registry_candidate_for_match(db: Session, job: LavoroVse, file_mtr: FileMtr | None, verification: VerificaVse | None) -> dict | None:
    if not file_mtr:
        return None
    data = build_final_pdf_data(job, file_mtr, verification)
    row_data = registry_data_from_pdf_data(job, file_mtr, verification, data)
    candidates = (
        db.query(RegistroApparecchiatura)
        .filter(
            RegistroApparecchiatura.owner_user_id == row_data.get("owner_user_id"),
            RegistroApparecchiatura.cliente_nome == row_data["cliente_nome"],
        )
        .all()
    )
    ranked = sorted(((registry_match_score(row, row_data), row) for row in candidates), key=lambda item: item[0]["score"], reverse=True)
    if not ranked or ranked[0][0]["score"] < 90:
        return None
    score, row = ranked[0]
    return {**_registry_dict(row), "match_score": score["score"], "match_reason": score["reason"]}


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


def _user_dict(row: Utente) -> dict:
    return {"id": row.id, "username": row.username, "nome": row.nome, "ruolo": row.ruolo, "attivo": row.attivo}


def _require_admin(user: Utente) -> None:
    if user.ruolo != "admin":
        raise HTTPException(status_code=403, detail="Permesso riservato agli amministratori")


def _is_admin(user: Utente) -> bool:
    return user.ruolo == "admin"


def _can_access_job(job: LavoroVse | None, user: Utente) -> bool:
    return bool(job and (_is_admin(user) or job.owner_user_id == user.id))


def _delete_job_pdf_files(job: LavoroVse) -> None:
    for row in job.pdf_generati or []:
        try:
            path = Path(row.percorso_pdf)
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            pass


def _can_access_registry(row: RegistroApparecchiatura, user: Utente) -> bool:
    return _is_admin(user) or row.owner_user_id == user.id
