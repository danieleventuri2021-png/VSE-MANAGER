from types import SimpleNamespace

from app.services.session_defaults_service import apply_defaults_to_verification


def test_apply_defaults_to_all_includes_presidio_and_reparto():
    job = SimpleNamespace(
        tecnico_default="",
        firma_default_path="",
        proprieta_default="",
        periodicita_default="12 mesi",
        tensione_default="220",
        frequenza_default="50",
        protezione_default="Trasformatore di isolamento",
        template_pdf="standard",
        intestazione_pdf="standard",
    )
    verification = SimpleNamespace(
        tecnico="",
        firma_path="",
        proprieta="",
        presidio="",
        reparto="",
        periodicita="",
        tensione="",
        frequenza="",
        protezione="",
        campi_bloccati_json={},
        dati_revisionati_json={},
    )

    changed = apply_defaults_to_verification(job, verification, {"presidio": "FISIOTER ONE", "reparto": "PALESTRA"})

    assert "presidio" in changed
    assert "reparto" in changed
    assert verification.dati_revisionati_json["presidio"] == "FISIOTER ONE"
    assert verification.dati_revisionati_json["reparto"] == "PALESTRA"
