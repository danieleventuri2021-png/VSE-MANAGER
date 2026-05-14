from app.models import Anomalia


def create_anomaly(db, lavoro_id: int, tipo: str, messaggio: str, severita: str = "warning", riferimenti: dict | None = None) -> Anomalia:
    anomaly = Anomalia(lavoro_id=lavoro_id, tipo=tipo, severita=severita, messaggio=messaggio, riferimenti=riferimenti or {})
    db.add(anomaly)
    return anomaly
