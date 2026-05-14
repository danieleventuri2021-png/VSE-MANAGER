from app.services.column_mapper import extract_row, map_columns


def test_map_columns_with_variable_names():
    mapping = map_columns(["N. Serie", "Marca", "Tipo", "Ubicazione"])
    assert mapping["matricola"] == "N. Serie"
    assert mapping["produttore"] == "Marca"
    assert mapping["modello"] == "Tipo"
    assert mapping["reparto"] == "Ubicazione"


def test_extract_row_cleans_values():
    row = extract_row({"Matricola": "  ABC123  "}, {"matricola": "Matricola"})
    assert row["matricola"] == "ABC123"
