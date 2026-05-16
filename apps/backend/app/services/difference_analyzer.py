IMPORTANT_FIELDS = ("matricola", "seriale", "inventario", "produttore", "modello", "descrizione", "reparto", "stanza", "esito")


def analyze_differences(equipment: dict, mtr: dict | None) -> dict:
    if not mtr:
        return {"missing_mtr": True, "fields": []}
    differences = []
    for field in IMPORTANT_FIELDS:
        excel_value = _norm(equipment.get(field))
        mtr_value = _norm(mtr.get(field))
        if excel_value and mtr_value and excel_value != mtr_value:
            differences.append({"field": field, "excel": equipment.get(field), "mtr": mtr.get(field)})
    return {"missing_mtr": False, "fields": differences}


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())
