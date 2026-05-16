from pathlib import Path

from app.services.esa615_legacy_adapter import (
    apply_template_defaults_legacy,
    default_class_legacy,
    default_earth_res_pos_legacy,
    default_installation_legacy,
    default_mobility_legacy,
    generate_pdf_legacy,
    sanitize_filename_legacy,
)


def build_pdf_filename(data: dict) -> str:
    legacy = to_legacy_edited(data)
    tip = sanitize_filename_legacy(legacy.get("tipologia", "") or "apparecchio")
    mfg = sanitize_filename_legacy(legacy.get("manufacturer", "") or "produttore")
    mod = sanitize_filename_legacy(legacy.get("model", "") or "modello")
    ser = sanitize_filename_legacy(legacy.get("serial", "") or "matricola")
    return f"{tip}-{mfg}-{mod}-{ser}.pdf"


def generate_vse_pdf(data: dict, output_dir: str | Path, template_pdf: str = "standard", header_image: str | None = None) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    legacy_data = _pdf_ready_data(to_legacy_data(data))
    legacy_edited = _pdf_ready_edited(apply_template_defaults_legacy(legacy_data, to_legacy_edited(data)))
    filename = build_pdf_filename({**data, **legacy_edited})
    path = output / filename
    generate_pdf_legacy(legacy_data, legacy_edited, path, header_image=header_image)
    return {"path": str(path), "filename": filename, "template_pdf": template_pdf}


def to_legacy_data(data: dict) -> dict:
    instrument = data.get("instrument") or {}
    measurements = [_to_legacy_measurement(item) for item in (data.get("measurements") or data.get("misure") or [])]
    legacy = {
        "sourceFile": data.get("source_file") or data.get("nome_file") or "",
        "sourceFilePath": data.get("source_path") or data.get("path_corrente") or "",
        "serialNumber": data.get("serialNumber") or data.get("serial_number") or data.get("seriale") or data.get("matricola") or "",
        "equipmentNumber": data.get("equipmentNumber") or data.get("invGest") or data.get("inventario") or "",
        "manufacturer": data.get("manufacturer") or data.get("produttore") or "",
        "model": data.get("model") or data.get("modello") or "",
        "location": data.get("stanza") or data.get("location") or data.get("presidio") or data.get("reparto") or "",
        "other": data.get("other") or data.get("tipologia") or data.get("descrizione") or "",
        "tipologia": data.get("tipologia") or data.get("other") or data.get("descrizione") or "",
        "templateName": data.get("templateName") or data.get("template_ansur") or "",
        "classification": data.get("classification") or data.get("classe") or data.get("classe_elettrica") or "I",
        "apType": data.get("apType") or data.get("parte_applicata") or "B",
        "testDate": data.get("testDate") or data.get("data_test") or data.get("data_verifica") or "",
        "overallStatus": _legacy_status(data.get("overallStatus") or data.get("esito_generale") or data.get("esito") or ""),
        "instrument": {
            "type": instrument.get("type") or data.get("strumento_tipo") or "ESA615",
            "serialNumber": instrument.get("serialNumber") or instrument.get("serial_number") or data.get("strumento_seriale") or "",
            "calibrationDate": instrument.get("calibrationDate") or instrument.get("calibration_date") or data.get("strumento_calibrazione") or "",
        },
        "measurements": measurements,
    }
    legacy["isPermanentThreeMeasure"] = "installazione permanente" in legacy["templateName"].lower() and "3 misure" in legacy["templateName"].lower()
    return legacy


def to_legacy_edited(data: dict) -> dict:
    legacy_data = to_legacy_data(data)
    edited = {
        "tipologia": data.get("tipologia") or data.get("descrizione") or legacy_data.get("tipologia", ""),
        "manufacturer": data.get("manufacturer") or data.get("produttore") or legacy_data.get("manufacturer", ""),
        "model": data.get("model") or data.get("modello") or legacy_data.get("model", ""),
        "serial": data.get("serial") or data.get("matricola") or data.get("seriale") or legacy_data.get("serialNumber", ""),
        "civab": data.get("civab") or data.get("CIVAB") or "",
        "proprieta": data.get("proprieta") or "",
        "invGest": data.get("invGest") or data.get("inventario") or legacy_data.get("equipmentNumber", ""),
        "invEnte": data.get("invEnte") or data.get("inventario_ente") or "",
        "presidio": data.get("presidio") or "",
        "reparto": data.get("reparto") or "",
        "stanza": data.get("stanza") or data.get("location") or legacy_data.get("location", ""),
        "periodicita": data.get("periodicita") or "12 mesi",
        "classe": data.get("classe") or data.get("classe_elettrica") or default_class_legacy(legacy_data),
        "apType": data.get("apType") or data.get("parte_applicata") or legacy_data.get("apType", "B"),
        "installazione": data.get("installazione") or default_installation_legacy(legacy_data),
        "mobilita": data.get("mobilita") or default_mobility_legacy(legacy_data),
        "tensione": data.get("tensione") or "220",
        "frequenza": data.get("frequenza") or "50",
        "potenza": data.get("potenza") or "",
        "potenza_unit": data.get("potenza_unit") or data.get("potenza_unita") or "W",
        "protezione": data.get("protezione") or "Trasformatore di isolamento",
        "fusibili_conformita": data.get("fusibili_conformita") or "",
        "dati_targa_fusibili": data.get("dati_targa_fusibili") or "",
        "valore_nominale": data.get("valore_nominale") or "",
        "protezione_altro": data.get("protezione_altro") or "",
        "vista_targa": data.get("vista_targa") or _visual_value(data, "targa"),
        "vista_telaio": data.get("vista_telaio") or _visual_value(data, "telaio"),
        "vista_parti_mov": data.get("vista_parti_mov") or _visual_value(data, "parti_mov"),
        "vista_cavo": data.get("vista_cavo") or _visual_value(data, "cavo"),
        "vista_passacavo": data.get("vista_passacavo") or _visual_value(data, "passacavo"),
        "vista_spie": data.get("vista_spie") or _visual_value(data, "spie"),
        "vista_parti_appl": data.get("vista_parti_appl") or _visual_value(data, "parti_appl"),
        "vista_doc": data.get("vista_doc") or _visual_value(data, "doc"),
        "tecnico": data.get("tecnico") or "",
        "firma_path": data.get("firma_path") or "",
        "earthResPos": data.get("earthResPos") or data.get("posizione_resistenza_terra") or default_earth_res_pos_legacy(legacy_data),
        "funz_accensione": data.get("funz_accensione") or "",
        "funz_prova_part": data.get("funz_prova_part") or "",
        "funz_codice_prot": data.get("funz_codice_prot") or "",
        "funz_normativa": data.get("funz_normativa") or "",
        "note": data.get("note") or "",
    }
    return edited


def _to_legacy_measurement(item: dict) -> dict:
    parent = item.get("parentType") or {
        "type": item.get("test_element") or item.get("testElement") or item.get("name") or item.get("nome") or "",
        "param": item.get("parameter") or item.get("condition") or "",
    }
    return {
        "description": item.get("description") or item.get("descrizione") or item.get("name") or item.get("nome") or "",
        "value": str(item.get("value") or item.get("valore") or ""),
        "unit": item.get("unit") or item.get("unita") or "",
        "status": _legacy_status(item.get("status") or item.get("result") or item.get("esito") or ""),
        "parentType": parent,
    }


def _legacy_status(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"passed", "pass", "ok", "conforme", "positivo"}:
        return "Passed"
    if text in {"failed", "fail", "ko", "non conforme", "negativo"}:
        return "Failed"
    return str(value or "")


def _visual_value(data: dict, key: str) -> str:
    visual = data.get("controlli_visivi") or data.get("esame_a_vista") or data.get("controlli_visivi_json") or {}
    return visual.get(key) or "OK"


def _pdf_ready_edited(data: dict) -> dict:
    keep_empty = {"firma_path"}
    return {key: (value if key in keep_empty or value not in (None, "") else "-") for key, value in data.items()}


def _pdf_ready_data(data: dict) -> dict:
    result = dict(data)
    for key in ("sourceFile", "serialNumber", "equipmentNumber", "manufacturer", "model", "location", "other", "tipologia", "templateName", "classification", "apType", "testDate", "overallStatus"):
        if result.get(key) in (None, ""):
            result[key] = "-"
    instrument = dict(result.get("instrument") or {})
    for key in ("type", "serialNumber", "calibrationDate"):
        if instrument.get(key) in (None, ""):
            instrument[key] = "-"
    result["instrument"] = instrument
    return result
