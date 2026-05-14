"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "gestione_vse"


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    op.create_table("clienti", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("nome", sa.String(255), nullable=False, unique=True), sa.Column("note", sa.Text()), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), schema=SCHEMA)
    op.create_table("presidi", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("cliente_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.clienti.id", ondelete="SET NULL")), sa.Column("nome", sa.String(255), nullable=False), sa.Column("indirizzo", sa.String(500)), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), schema=SCHEMA)
    op.create_table("lavori_vse", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("titolo", sa.String(255), nullable=False), sa.Column("cliente_nome", sa.String(255)), sa.Column("presidio_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.presidi.id", ondelete="SET NULL")), sa.Column("stato", sa.String(50), nullable=False), sa.Column("excel_path", sa.String(1000)), sa.Column("mtr_folder", sa.String(1000)), sa.Column("summary", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), schema=SCHEMA)
    op.create_table("file_mtr", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("lavoro_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"), nullable=False), sa.Column("path_originale", sa.String(1000), nullable=False), sa.Column("path_corrente", sa.String(1000), nullable=False), sa.Column("nome_file", sa.String(255), nullable=False), sa.Column("matricola", sa.String(255)), sa.Column("seriale", sa.String(255)), sa.Column("inventario", sa.String(255)), sa.Column("produttore", sa.String(255)), sa.Column("modello", sa.String(255)), sa.Column("descrizione", sa.Text()), sa.Column("reparto", sa.String(255)), sa.Column("parsed_data", postgresql.JSONB(), nullable=False), sa.Column("stato", sa.String(50), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), schema=SCHEMA)
    op.create_table("apparecchiature", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("lavoro_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"), nullable=False), sa.Column("row_index", sa.Integer(), nullable=False), sa.Column("matricola", sa.String(255)), sa.Column("seriale", sa.String(255)), sa.Column("inventario", sa.String(255)), sa.Column("produttore", sa.String(255)), sa.Column("modello", sa.String(255)), sa.Column("descrizione", sa.Text()), sa.Column("reparto", sa.String(255)), sa.Column("raw_data", postgresql.JSONB(), nullable=False), sa.Column("match_status", sa.String(50), nullable=False), sa.Column("match_score", sa.Float()), sa.Column("matched_file_mtr_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.file_mtr.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("lavoro_id", "row_index", name="uq_apparecchiature_lavoro_riga"), schema=SCHEMA)
    op.create_table("verifiche_vse", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("apparecchiatura_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.apparecchiature.id", ondelete="CASCADE")), sa.Column("esito_excel", sa.String(100)), sa.Column("esito_mtr", sa.String(100)), sa.Column("data_verifica", sa.String(100)), sa.Column("differenze", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), schema=SCHEMA)
    op.create_table("misure_vse", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("verifica_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.verifiche_vse.id", ondelete="CASCADE")), sa.Column("nome", sa.String(255), nullable=False), sa.Column("valore_excel", sa.String(255)), sa.Column("valore_mtr", sa.String(255)), sa.Column("unita", sa.String(50)), sa.Column("esito", sa.String(50)), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), schema=SCHEMA)
    op.create_table("anomalie", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("lavoro_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE"), nullable=False), sa.Column("tipo", sa.String(100), nullable=False), sa.Column("severita", sa.String(50), nullable=False), sa.Column("messaggio", sa.Text(), nullable=False), sa.Column("stato", sa.String(50), nullable=False), sa.Column("riferimenti", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), schema=SCHEMA)
    op.create_table("log_operativo", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("lavoro_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.lavori_vse.id", ondelete="CASCADE")), sa.Column("livello", sa.String(50), nullable=False), sa.Column("evento", sa.String(255), nullable=False), sa.Column("messaggio", sa.Text(), nullable=False), sa.Column("dettagli", postgresql.JSONB(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), schema=SCHEMA)


def downgrade() -> None:
    for table in ["log_operativo", "anomalie", "misure_vse", "verifiche_vse", "apparecchiature", "file_mtr", "lavori_vse", "presidi", "clienti"]:
        op.drop_table(table, schema=SCHEMA)
