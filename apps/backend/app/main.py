from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.routes import auth_router, dashboard_counts, database_status, router
from app.core.config import get_settings
from app.db.session import Base, SessionLocal, engine, ensure_schema, get_db
from app.services.auth_service import ensure_default_admin, get_current_user

settings = get_settings()

app = FastAPI(title="gestione-vse", version="0.1.0")

_cors_origins = list({settings.frontend_origin, *settings.cors_origins_list})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Accept-Language", "Content-Language", "Content-Type", "Authorization", "X-Requested-With"],
)
app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api", dependencies=[Depends(get_current_user)])


@app.on_event("startup")
def startup() -> None:
    try:
        ensure_schema()
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            ensure_default_admin(db)
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
