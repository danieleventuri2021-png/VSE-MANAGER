from app.api.routes import _assign_missing_device_identifiers


def test_assign_missing_device_identifiers_distinguishes_equal_devices_without_ids():
    parsed_files = [
        {"nome_file": "b.mtr", "descrizione": "Letto", "produttore": "Chinesport", "modello": "X", "normalized": {"dut": {"description": "Letto", "manufacturer": "Chinesport", "model": "X"}}},
        {"nome_file": "a.mtr", "descrizione": "Letto", "produttore": "Chinesport", "modello": "X", "normalized": {"dut": {"description": "Letto", "manufacturer": "Chinesport", "model": "X"}}},
    ]
    _assign_missing_device_identifiers(parsed_files)
    assert [item["inventario"] for item in sorted(parsed_files, key=lambda item: item["nome_file"])] == ["Disp1", "Disp2"]
    assert parsed_files[0]["normalized"]["dut"]["inventory"] == "Disp2"
