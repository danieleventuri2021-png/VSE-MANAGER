from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.routes import dashboard_counts, database_status, router
from app.core.config import get_settings
from app.db.session import Base, engine, ensure_schema, get_db

settings = get_settings()

app = FastAPI(title="gestione-vse", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    try:
        ensure_schema()
        Base.metadata.create_all(bind=engine)
        app.state.database_ready = True
        app.state.database_error = None
    except Exception as exc:
        app.state.database_ready = False
        app.state.database_error = str(exc)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = database_status(db)
    counts = dashboard_counts(db) if db_ok else {"jobs": 0, "open_anomalies": 0}
    return {
        "status": "ok",
        "app": "gestione-vse",
        "database": db_ok,
        "database_error": None if db_ok else getattr(app.state, "database_error", None),
        "backend_port": settings.backend_port,
        "frontend_origin": settings.frontend_origin,
        **counts,
    }
