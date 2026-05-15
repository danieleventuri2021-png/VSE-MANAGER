from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.session import Base

SCHEMA = get_settings().db_schema


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Cliente(Base, TimestampMixin):
    __tablename__ = "clienti"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    note: Mapped[str | None] = mapped_column(Text)
    presidi: Mapped[list["Presidio"]] = relationship(back_populates="cliente")


class Presidio(Base, TimestampMixin):
    __tablename__ = "presidi"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.clienti.id", ondelete="SET NULL"))
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    indirizzo: Mapped[str | None] = mapped_column(String(500))
    cliente: Mapped[Cliente | None] = relationship(back_populates="presidi")
    lavori: Mapped[list["LavoroVse"]] = relationship(back_populates="presidio")


class Utente(Base, TimestampMixin):
    __tablename__ = "utenti"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str | None] = mapped_column(String(255))
    ruolo: Mapped[str] = mapped_column(String(50), default="admin", nullable=False)
    attivo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lavori: Mapped[list["LavoroVse"]] = relationship(back_populates="owner")
    registro_apparecchiature: Mapped[list["RegistroApparecchiatura"]] = relationship(back_populates="owner")


class LavoroVse(Base, TimestampMixin):
    __tablename__ = "lavori_vse"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    titolo: Mapped[str] = mapped_column(String(255), nullable=False)
    cliente_nome: Mapped[str | None] = mapped_column(String(255))
    presidio_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.presidi.id", ondelete="SET NULL"))
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.utenti.id", ondelete="SET NULL"), index=True)
    stato: Mapped[str] = mapped_column(String(50), default="non_elaborato", nullable=False)
    excel_path: Mapped[str | None] = mapped_column(String(1000))
    mtr_folder: Mapped[str | None] = mapped_column(String(1000))
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    tecnico_default: Mapped[str | None] = mapped_column(String(255))
    firma_default_path: Mapped[str | None] = mapped_column(String(1000))
    proprieta_default: Mapped[str | None] = mapped_column(String(255))
    periodicita_default: Mapped[str | None] = mapped_column(String(50), default="12")
    tensione_default: Mapped[str | None] = mapped_column(String(50), default="220")
    frequenza_default: Mapped[str | None] = mapped_column(String(50), default="50")
    protezione_default: Mapped[str | None] = mapped_column(String(255), default="Trasformatore di isolamento")
    template_pdf: Mapped[str | None] = mapped_column(String(100), default="standard")
    intestazione_pdf: Mapped[str | None] = mapped_column(String(100), default="standard")
    owner: Mapped[Utente | None] = relationship(back_populates="lavori")
    presidio: Mapped[Presidio | None] = relationship(back_populates="lavori")
    apparecchiature: Mapped[list["Apparecchiatura"]] = relationship(back_populates="lavoro", cascade="all, delete-orphan")
    file_mtr: Mapped[list["FileMtr"]] = relationship(back_populates="lavoro", cascade="all, delete-orphan")
    anomalie: Mapped[list["Anomalia"]] = relationship(back_populates="lavoro", cascade="all, delete-orphan")
    logs: Mapped[list["LogOperativo"]] = relationship(back_populates="lavoro", cascade="all, delete-orphan")
    pdf_generati: Mapped[list["PdfGenerato"]] = relationship(back_populates="lavoro", cascade="all, delete-orphan")
    registro_apparecchiature: Mapped[list["RegistroApparecchiatura"]] = relationship(back_populates="ultimo_lavoro")


class Apparecchiatura(Base, TimestampMixin):
    __tablename__ = "apparecchiature"
    __table_args__ = (
        UniqueConstraint("lavoro_id", "row_index", name="uq_apparecchiature_lavoro_riga"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lavoro_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"), nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    matricola: Mapped[str | None] = mapped_column(String(255), index=True)
    seriale: Mapped[str | None] = mapped_column(String(255), index=True)
    inventario: Mapped[str | None] = mapped_column(String(255), index=True)
    produttore: Mapped[str | None] = mapped_column(String(255))
    modello: Mapped[str | None] = mapped_column(String(255))
    descrizione: Mapped[str | None] = mapped_column(Text)
    reparto: Mapped[str | None] = mapped_column(String(255))
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    match_status: Mapped[str] = mapped_column(String(50), default="non_elaborato", nullable=False)
    match_score: Mapped[float | None] = mapped_column(Float)
    matched_file_mtr_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.file_mtr.id", ondelete="SET NULL"))
    lavoro: Mapped[LavoroVse] = relationship(back_populates="apparecchiature")
    matched_file_mtr: Mapped["FileMtr | None"] = relationship(back_populates="matched_apparecchiature")
    verifiche: Mapped[list["VerificaVse"]] = relationship(back_populates="apparecchiatura", cascade="all, delete-orphan")


class VerificaVse(Base, TimestampMixin):
    __tablename__ = "verifiche_vse"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    apparecchiatura_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.apparecchiature.id", ondelete="CASCADE"))
    file_mtr_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.file_mtr.id", ondelete="CASCADE"))
    esito_excel: Mapped[str | None] = mapped_column(String(100))
    esito_mtr: Mapped[str | None] = mapped_column(String(100))
    data_verifica: Mapped[str | None] = mapped_column(String(100))
    differenze: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    tecnico: Mapped[str | None] = mapped_column(String(255))
    firma_path: Mapped[str | None] = mapped_column(String(1000))
    proprieta: Mapped[str | None] = mapped_column(String(255))
    periodicita: Mapped[str | None] = mapped_column(String(50))
    tensione: Mapped[str | None] = mapped_column(String(50))
    frequenza: Mapped[str | None] = mapped_column(String(50))
    potenza: Mapped[str | None] = mapped_column(String(50))
    potenza_unita: Mapped[str | None] = mapped_column(String(20))
    protezione: Mapped[str | None] = mapped_column(String(255))
    installazione: Mapped[str | None] = mapped_column(String(100))
    mobilita: Mapped[str | None] = mapped_column(String(100))
    classe_elettrica: Mapped[str | None] = mapped_column(String(50))
    parte_applicata: Mapped[str | None] = mapped_column(String(50))
    controlli_visivi_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    controlli_funzionali_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    stato_revisione: Mapped[str] = mapped_column(String(50), default="da_revisionare", nullable=False)
    campi_bloccati_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    dati_revisionati_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    dati_ansur_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    dati_excel_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    dati_finali_pdf_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    apparecchiatura: Mapped[Apparecchiatura] = relationship(back_populates="verifiche")
    file_mtr: Mapped["FileMtr | None"] = relationship(back_populates="verifiche")
    misure: Mapped[list["MisuraVse"]] = relationship(back_populates="verifica", cascade="all, delete-orphan")
    pdf_generati: Mapped[list["PdfGenerato"]] = relationship(back_populates="verifica")


class MisuraVse(Base, TimestampMixin):
    __tablename__ = "misure_vse"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    verifica_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.verifiche_vse.id", ondelete="CASCADE"))
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    valore_excel: Mapped[str | None] = mapped_column(String(255))
    valore_mtr: Mapped[str | None] = mapped_column(String(255))
    unita: Mapped[str | None] = mapped_column(String(50))
    esito: Mapped[str | None] = mapped_column(String(50))
    verifica: Mapped[VerificaVse] = relationship(back_populates="misure")


class FileMtr(Base, TimestampMixin):
    __tablename__ = "file_mtr"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lavoro_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"), nullable=False)
    path_originale: Mapped[str] = mapped_column(String(1000), nullable=False)
    path_corrente: Mapped[str] = mapped_column(String(1000), nullable=False)
    nome_file: Mapped[str] = mapped_column(String(255), nullable=False)
    matricola: Mapped[str | None] = mapped_column(String(255), index=True)
    seriale: Mapped[str | None] = mapped_column(String(255), index=True)
    inventario: Mapped[str | None] = mapped_column(String(255), index=True)
    produttore: Mapped[str | None] = mapped_column(String(255))
    modello: Mapped[str | None] = mapped_column(String(255))
    descrizione: Mapped[str | None] = mapped_column(Text)
    reparto: Mapped[str | None] = mapped_column(String(255))
    parsed_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="mtr", nullable=False)
    template_ansur: Mapped[str | None] = mapped_column(String(255))
    is_permanent_three_measure_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parsed_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    measurement_index_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_source_write_at: Mapped[datetime | None] = mapped_column(DateTime)
    stato: Mapped[str] = mapped_column(String(50), default="non_elaborato", nullable=False)
    lavoro: Mapped[LavoroVse] = relationship(back_populates="file_mtr")
    matched_apparecchiature: Mapped[list[Apparecchiatura]] = relationship(back_populates="matched_file_mtr")
    verifiche: Mapped[list[VerificaVse]] = relationship(back_populates="file_mtr")
    pdf_generati: Mapped[list["PdfGenerato"]] = relationship(back_populates="file_mtr")


class Anomalia(Base, TimestampMixin):
    __tablename__ = "anomalie"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lavoro_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(100), nullable=False)
    severita: Mapped[str] = mapped_column(String(50), default="warning", nullable=False)
    messaggio: Mapped[str] = mapped_column(Text, nullable=False)
    stato: Mapped[str] = mapped_column(String(50), default="aperta", nullable=False)
    riferimenti: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    lavoro: Mapped[LavoroVse] = relationship(back_populates="anomalie")


class LogOperativo(Base, TimestampMixin):
    __tablename__ = "log_operativo"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lavoro_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"))
    livello: Mapped[str] = mapped_column(String(50), default="INFO", nullable=False)
    evento: Mapped[str] = mapped_column(String(255), nullable=False)
    messaggio: Mapped[str] = mapped_column(Text, nullable=False)
    dettagli: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    lavoro: Mapped[LavoroVse | None] = relationship(back_populates="logs")


class PdfGenerato(Base):
    __tablename__ = "pdf_generati"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lavoro_id: Mapped[int] = mapped_column(ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"), nullable=False)
    verifica_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.verifiche_vse.id", ondelete="SET NULL"))
    file_mtr_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.file_mtr.id", ondelete="SET NULL"))
    percorso_pdf: Mapped[str] = mapped_column(String(1000), nullable=False)
    nome_pdf: Mapped[str] = mapped_column(String(255), nullable=False)
    template_pdf: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    esito: Mapped[str] = mapped_column(String(50), default="generato", nullable=False)
    errore: Mapped[str | None] = mapped_column(Text)
    lavoro: Mapped[LavoroVse] = relationship(back_populates="pdf_generati")
    verifica: Mapped[VerificaVse | None] = relationship(back_populates="pdf_generati")
    file_mtr: Mapped[FileMtr | None] = relationship(back_populates="pdf_generati")


class RegistroApparecchiatura(Base, TimestampMixin):
    __tablename__ = "registro_apparecchiature"
    __table_args__ = (
        UniqueConstraint("cliente_nome", "identificativo", name="uq_registro_cliente_identificativo"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.utenti.id", ondelete="SET NULL"), index=True)
    cliente_nome: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    presidio: Mapped[str | None] = mapped_column(String(255))
    reparto: Mapped[str | None] = mapped_column(String(255))
    stanza: Mapped[str | None] = mapped_column(String(255))
    ubicazione: Mapped[str | None] = mapped_column(String(500))
    tipologia: Mapped[str | None] = mapped_column(String(255))
    produttore: Mapped[str | None] = mapped_column(String(255), index=True)
    modello: Mapped[str | None] = mapped_column(String(255), index=True)
    matricola: Mapped[str | None] = mapped_column(String(255), index=True)
    seriale: Mapped[str | None] = mapped_column(String(255), index=True)
    inventario_gestionale: Mapped[str | None] = mapped_column(String(255), index=True)
    inventario_ente: Mapped[str | None] = mapped_column(String(255))
    civab: Mapped[str | None] = mapped_column(String(255))
    identificativo: Mapped[str] = mapped_column(String(255), nullable=False)
    data_ultima_verifica: Mapped[str | None] = mapped_column(String(50))
    periodicita_mesi: Mapped[int | None] = mapped_column(Integer)
    data_prossima_verifica: Mapped[str | None] = mapped_column(String(50), index=True)
    esito_ultima_verifica: Mapped[str | None] = mapped_column(String(100))
    tecnico_ultima_verifica: Mapped[str | None] = mapped_column(String(255))
    ultimo_lavoro_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="SET NULL"))
    ultimo_file_mtr_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.file_mtr.id", ondelete="SET NULL"))
    ultima_verifica_id: Mapped[int | None] = mapped_column(ForeignKey(f"{SCHEMA}.verifiche_vse.id", ondelete="SET NULL"))
    calendar_event_id: Mapped[str | None] = mapped_column(String(255))
    raw_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    owner: Mapped[Utente | None] = relationship(back_populates="registro_apparecchiature")
    ultimo_lavoro: Mapped[LavoroVse | None] = relationship(back_populates="registro_apparecchiature")
