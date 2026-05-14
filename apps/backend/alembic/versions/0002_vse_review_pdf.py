"""review fields and pdf generation

Revision ID: 0002_vse_review_pdf
Revises: 0001_initial
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_vse_review_pdf"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

SCHEMA = "gestione_vse"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def has_column(table: str, column: str) -> bool:
        return column in {item["name"] for item in inspector.get_columns(table, schema=SCHEMA)}

    def add_if_missing(table: str, column: sa.Column) -> None:
        if not has_column(table, column.name):
            op.add_column(table, column, schema=SCHEMA)

    op.alter_column("verifiche_vse", "apparecchiatura_id", existing_type=sa.Integer(), nullable=True, schema=SCHEMA)

    for name, column in {
        "tecnico_default": sa.Column("tecnico_default", sa.String(255)),
        "firma_default_path": sa.Column("firma_default_path", sa.String(1000)),
        "proprieta_default": sa.Column("proprieta_default", sa.String(255)),
        "periodicita_default": sa.Column("periodicita_default", sa.String(50), server_default="12"),
        "tensione_default": sa.Column("tensione_default", sa.String(50), server_default="220"),
        "frequenza_default": sa.Column("frequenza_default", sa.String(50), server_default="50"),
        "protezione_default": sa.Column("protezione_default", sa.String(255), server_default="Trasformatore di isolamento"),
        "template_pdf": sa.Column("template_pdf", sa.String(100), server_default="standard"),
        "intestazione_pdf": sa.Column("intestazione_pdf", sa.String(100), server_default="standard"),
    }.items():
        add_if_missing("lavori_vse", column)

    for column in [
        sa.Column("source_type", sa.String(50), nullable=False, server_default="mtr"),
        sa.Column("template_ansur", sa.String(255)),
        sa.Column("is_permanent_three_measure_template", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("parsed_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("measurement_index_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_source_write_at", sa.DateTime()),
    ]:
        add_if_missing("file_mtr", column)

    add_if_missing("verifiche_vse", sa.Column("file_mtr_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.file_mtr.id", ondelete="CASCADE")))
    for column in [
        sa.Column("tecnico", sa.String(255)),
        sa.Column("firma_path", sa.String(1000)),
        sa.Column("proprieta", sa.String(255)),
        sa.Column("periodicita", sa.String(50)),
        sa.Column("tensione", sa.String(50)),
        sa.Column("frequenza", sa.String(50)),
        sa.Column("potenza", sa.String(50)),
        sa.Column("potenza_unita", sa.String(20)),
        sa.Column("protezione", sa.String(255)),
        sa.Column("installazione", sa.String(100)),
        sa.Column("mobilita", sa.String(100)),
        sa.Column("classe_elettrica", sa.String(50)),
        sa.Column("parte_applicata", sa.String(50)),
        sa.Column("controlli_visivi_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("controlli_funzionali_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("note", sa.Text()),
        sa.Column("stato_revisione", sa.String(50), nullable=False, server_default="da_revisionare"),
        sa.Column("campi_bloccati_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dati_revisionati_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dati_ansur_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dati_excel_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("dati_finali_pdf_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    ]:
        add_if_missing("verifiche_vse", column)

    if "pdf_generati" not in inspector.get_table_names(schema=SCHEMA):
        op.create_table(
            "pdf_generati",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("lavoro_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"), nullable=False),
            sa.Column("verifica_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.verifiche_vse.id", ondelete="SET NULL")),
            sa.Column("file_mtr_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.file_mtr.id", ondelete="SET NULL")),
            sa.Column("percorso_pdf", sa.String(1000), nullable=False),
            sa.Column("nome_pdf", sa.String(255), nullable=False),
            sa.Column("template_pdf", sa.String(100)),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("esito", sa.String(50), nullable=False),
            sa.Column("errore", sa.Text()),
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("pdf_generati", schema=SCHEMA)
    for name in [
        "dati_finali_pdf_json", "dati_excel_json", "dati_ansur_json", "dati_revisionati_json", "campi_bloccati_json",
        "stato_revisione", "note", "controlli_funzionali_json", "controlli_visivi_json", "parte_applicata",
        "classe_elettrica", "mobilita", "installazione", "protezione", "potenza_unita", "potenza", "frequenza",
        "tensione", "periodicita", "proprieta", "firma_path", "tecnico", "file_mtr_id",
    ]:
        op.drop_column("verifiche_vse", name, schema=SCHEMA)
    for name in ["last_source_write_at", "measurement_index_json", "parsed_json", "is_permanent_three_measure_template", "template_ansur", "source_type"]:
        op.drop_column("file_mtr", name, schema=SCHEMA)
    for name in ["intestazione_pdf", "template_pdf", "protezione_default", "frequenza_default", "tensione_default", "periodicita_default", "proprieta_default", "firma_default_path", "tecnico_default"]:
        op.drop_column("lavori_vse", name, schema=SCHEMA)
