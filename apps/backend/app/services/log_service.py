from app.models import LogOperativo


def log_event(db, evento: str, messaggio: str, lavoro_id: int | None = None, livello: str = "INFO", dettagli: dict | None = None) -> LogOperativo:
    row = LogOperativo(lavoro_id=lavoro_id, livello=livello, evento=evento, messaggio=messaggio, dettagli=dettagli or {})
    db.add(row)
    return row
