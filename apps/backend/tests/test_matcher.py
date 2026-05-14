from app.services.matcher import match_records


def test_matcher_exact_serial_is_certain():
    equipment = [{"matricola": "SN123", "produttore": "Fluke", "modello": "ESA615"}]
    mtr = [{"matricola": "SN123", "produttore": "Fluke", "modello": "ESA615"}]
    matches, orphans = match_records(equipment, mtr)
    assert matches[0].status == "certo"
    assert matches[0].score == 100
    assert orphans == []


def test_matcher_reports_orphan():
    matches, orphans = match_records([{"matricola": "A"}], [{"matricola": "B"}])
    assert matches[0].status == "mancante"
    assert orphans == [0]
