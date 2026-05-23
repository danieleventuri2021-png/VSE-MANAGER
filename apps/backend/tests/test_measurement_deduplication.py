from types import SimpleNamespace

from app.services.measurement_deduplication_service import measurement_count, measurement_key_from_parsed, normalized_measurement_date


def test_normalized_measurement_date_accepts_italian_dates():
    assert normalized_measurement_date("14/04/2026 09:30:00") == "2026-04-14"
    assert normalized_measurement_date("2026-04-14T09:30:00") == "2026-04-14"


def test_measurement_key_uses_equipment_identifier_and_test_day():
    job = SimpleNamespace(owner_user_id=7, cliente_nome="Cliente Demo")
    parsed = {
        "nome_file": "test.mtr",
        "matricola": " SN-001 ",
        "normalized": {
            "test": {"date": "14/04/2026"},
            "measurements": [{"name": "PE", "value": "0.1"}, {"name": "Leakage", "value": "1.0"}],
        },
    }
    key = measurement_key_from_parsed(job, parsed)
    assert key.identificativo == "SN001"
    assert key.data_verifica == "2026-04-14"
    assert measurement_count(parsed) == 2
