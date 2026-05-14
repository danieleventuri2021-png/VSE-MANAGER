from app.services.measurement_indexer import normalize_text
from app.services.measurement_selector import find_protective_earth_measurements


PERMANENT_WORDS = ("installazione permanente", "permanent installation", "permanente", "permanent", "impianto fisso")


def is_permanent_three_measure_template(template_name: str | None, measurements: list[dict]) -> bool:
    name = normalize_text(template_name)
    has_name_hint = any(normalize_text(word) in name for word in PERMANENT_WORDS)
    protective_earth = find_protective_earth_measurements(measurements)
    return has_name_hint and len(protective_earth) >= 3
