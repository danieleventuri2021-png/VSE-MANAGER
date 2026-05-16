from typing import Any

from app.models import LavoroVse, VerificaVse
from app.services.vse_defaults import job_defaults


DEFAULT_FIELDS = ("tecnico", "firma_path", "proprieta", "periodicita", "tensione", "frequenza", "protezione")


def update_job_defaults(job: LavoroVse, values: dict[str, Any]) -> None:
    mapping = {
        "tecnico": "tecnico_default",
        "firma_path": "firma_default_path",
        "proprieta": "proprieta_default",
        "periodicita": "periodicita_default",
        "tensione": "tensione_default",
        "frequenza": "frequenza_default",
        "protezione": "protezione_default",
        "template_pdf": "template_pdf",
        "intestazione_pdf": "intestazione_pdf",
    }
    for source, target in mapping.items():
        if source in values:
            setattr(job, target, values[source])


def apply_defaults_to_verification(job: LavoroVse, verification: VerificaVse, values: dict[str, Any] | None = None) -> list[str]:
    defaults = {**job_defaults(job), **(values or {})}
    locked = verification.campi_bloccati_json or {}
    changed = []
    for field in DEFAULT_FIELDS:
        if locked.get(field):
            continue
        value = defaults.get(field)
        if value is not None and getattr(verification, field, None) != value:
            setattr(verification, field, value)
            verification.dati_revisionati_json = {**(verification.dati_revisionati_json or {}), field: value}
            changed.append(field)
    return changed
