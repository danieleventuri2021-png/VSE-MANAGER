"""equipment registry

Revision ID: 0003_equipment_registry
Revises: 0002_vse_review_pdf
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_equipment_registry"
down_revision = "0002_vse_review_pdf"
branch_labels = None
depends_on = None

SCHEMA = "gestione_vse"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "registro_apparecchiature" in inspector.get_table_names(schema=SCHEMA):
        return
    op.create_table(
        "registro_apparecchiature",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente_nome", sa.String(255), nullable=False),
        sa.Column("presidio", sa.String(255)),
        sa.Column("reparto", sa.String(255)),
        sa.Column("stanza", sa.String(255)),
        sa.Column("ubicazione", sa.String(500)),
        sa.Column("tipologia", sa.String(255)),
        sa.Column("produttore", sa.String(255)),
        sa.Column("modello", sa.String(255)),
        sa.Column("matricola", sa.String(255)),
        sa.Column("seriale", sa.String(255)),
        sa.Column("inventario_gestionale", sa.String(255)),
        sa.Column("inventario_ente", sa.String(255)),
        sa.Column("civab", sa.String(255)),
        sa.Column("identificativo", sa.String(255), nullable=False),
        sa.Column("data_ultima_verifica", sa.String(50)),
        sa.Column("periodicita_mesi", sa.Integer()),
        sa.Column("data_prossima_verifica", sa.String(50)),
        sa.Column("esito_ultima_verifica", sa.String(100)),
        sa.Column("tecnico_ultima_verifica", sa.String(255)),
        sa.Column("ultimo_lavoro_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="SET NULL")),
        sa.Column("ultimo_file_mtr_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.file_mtr.id", ondelete="SET NULL")),
        sa.Column("ultima_verifica_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.verifiche_vse.id", ondelete="SET NULL")),
        sa.Column("calendar_event_id", sa.String(255)),
        sa.Column("raw_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("cliente_nome", "identificativo", name="uq_registro_cliente_identificativo"),
        schema=SCHEMA,
    )
    op.create_index("ix_registro_cliente", "registro_apparecchiature", ["cliente_nome"], schema=SCHEMA)
    op.create_index("ix_registro_scadenza", "registro_apparecchiature", ["data_prossima_verifica"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("registro_apparecchiature", schema=SCHEMA)
