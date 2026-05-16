from copy import deepcopy
from typing import Any

from app.services.measurement_selector import find_worst_protective_earth


SYSTEM_DEFAULTS: dict[str, Any] = {
    "periodicita": "12",
    "tensione": "220",
    "frequenza": "50",
    "potenza": "",
    "potenza_unita": "W",
    "protezione": "Trasformatore di isolamento",
    "esame_a_vista": {"involucro": "OK", "cavo": "OK", "spina": "OK", "etichette": "OK"},
    "controlli_funzionali": {},
    "note": "",
    "reparto": "",
    "stanza": "",
    "inventario_ente": "",
    "civab": "",
}


def job_defaults(job: Any) -> dict[str, Any]:
    return {
        **SYSTEM_DEFAULTS,
        "tecnico": getattr(job, "tecnico_default", None) or "",
        "firma_path": getattr(job, "firma_default_path", None) or "",
        "proprieta": getattr(job, "proprieta_default", None) or "",
        "periodicita": getattr(job, "periodicita_default", None) or SYSTEM_DEFAULTS["periodicita"],
        "tensione": getattr(job, "tensione_default", None) or SYSTEM_DEFAULTS["tensione"],
        "frequenza": getattr(job, "frequenza_default", None) or SYSTEM_DEFAULTS["frequenza"],
        "protezione": getattr(job, "protezione_default", None) or SYSTEM_DEFAULTS["protezione"],
        "template_pdf": getattr(job, "template_pdf", None) or "standard",
        "intestazione_pdf": getattr(job, "intestazione_pdf", None) or "standard",
    }


def ansur_defaults(parsed: dict) -> dict[str, Any]:
    ansur = parsed.get("ansur") or {}
    measurements = parsed.get("measurements") or []
    result = {
        "classe_elettrica": ansur.get("electrical_class") or "I",
        "parte_applicata": ansur.get("applied_part_type") or "",
        "installazione": "Non permanente",
        "mobilita": "Trasportabile",
        "posizione_resistenza_terra": "Connettore terra spina/parti accessibili",
    }
    if ansur.get("is_permanent_three_measure_template"):
        worst = find_worst_protective_earth(measurements)
        result.update(
            {
                "classe_elettrica": "I",
                "installazione": "Permanente",
                "mobilita": "Fisso",
                "posizione_resistenza_terra": "Installazione permanente - peggiore misura PE",
                "resistenza_terra": worst.get("value") if worst else "",
            }
        )
    return result


def source_data(parsed: dict) -> dict[str, Any]:
    dut = parsed.get("dut") or {}
    test = parsed.get("test") or {}
    instrument = parsed.get("instrument") or {}
    ansur = parsed.get("ansur") or {}
    return {
        "produttore": dut.get("manufacturer") or "",
        "modello": dut.get("model") or "",
        "matricola": dut.get("serial_number") or "",
        "inventario": dut.get("inventory") or "",
        "descrizione": dut.get("description") or "",
        "presidio": "",
        "reparto": dut.get("department") or "",
        "stanza": dut.get("location") or "",
        "template_ansur": ansur.get("template_name") or "",
        "classe_elettrica": ansur.get("electrical_class") or "",
        "parte_applicata": ansur.get("applied_part_type") or "",
        "data_test": test.get("date") or "",
        "esito_generale": test.get("status") or "",
        "strumento_tipo": instrument.get("type") or "",
        "strumento_produttore": instrument.get("manufacturer") or "",
        "strumento_seriale": instrument.get("serial_number") or "",
        "strumento_calibrazione": instrument.get("calibration_date") or "",
    }


def merge_final_data(
    *,
    system_defaults: dict | None = None,
    job_defaults_data: dict | None = None,
    ansur_data: dict | None = None,
    excel_data: dict | None = None,
    revised_data: dict | None = None,
    locked_data: dict | None = None,
) -> dict[str, Any]:
    final = deepcopy(system_defaults or SYSTEM_DEFAULTS)
    for layer in (job_defaults_data or {}, ansur_data or {}, excel_data or {}, revised_data or {}, locked_data or {}):
        for key, value in layer.items():
            if value is not None and value != "":
                final[key] = value
    return final
