from datetime import date
from types import SimpleNamespace

from app.services.equipment_registry_service import add_months, build_registry_ics, parse_periodicity_months, registry_data_from_pdf_data, registry_match_score


def test_periodicity_and_next_due_date():
    assert parse_periodicity_months("12 mesi") == 12
    assert add_months(date(2026, 4, 14), 12).isoformat() == "2027-04-14"


def test_registry_data_from_pdf_data():
    job = SimpleNamespace(id=7, cliente_nome="Cliente Demo", periodicita_default="24")
    file_mtr = SimpleNamespace(id=11, matricola="SN1", seriale="SN1", inventario="", produttore="Acme", modello="X1", descrizione="Monitor", reparto="AMB A")
    verification = SimpleNamespace(id=13)
    data = {"tipologia": "Monitor", "manufacturer": "Acme", "model": "X1", "serial": "SN1", "presidio": "Sede", "reparto": "AMB A", "testDate": "14/04/2026", "periodicita": "12 mesi", "overallStatus": "Passed"}
    row = registry_data_from_pdf_data(job, file_mtr, verification, data)
    assert row["identificativo"] == "SN1"
    assert row["data_ultima_verifica"] == "2026-04-14"
    assert row["data_prossima_verifica"] == "2027-04-14"


def test_registry_ics_export():
    row = SimpleNamespace(id=1, identificativo="SN1", data_prossima_verifica="2027-04-14", cliente_nome="Cliente Demo", tipologia="Monitor", produttore="Acme", modello="X1", matricola="SN1", ubicazione="AMB A")
    ics = build_registry_ics([row])
    assert "BEGIN:VCALENDAR" in ics
    assert "DTSTART;VALUE=DATE:20270414" in ics
    assert "VSE Cliente Demo - Monitor" in ics


def test_registry_match_uses_inventory_when_serial_changes():
    row = SimpleNamespace(matricola="", seriale="", identificativo="INV08", inventario_gestionale="08", inventario_ente="", tipologia="Tecar", produttore="Golden Star", modello="Endor Plus")
    incoming = {"matricola": "SN-NEW", "seriale": "SN-NEW", "identificativo": "SNNEW", "inventario_gestionale": "08", "inventario_ente": "", "tipologia": "Tecar", "produttore": "Golden Star", "modello": "Endor Plus"}
    match = registry_match_score(row, incoming)
    assert match["score"] >= 90
    assert "INVGEST" in match["reason"]
