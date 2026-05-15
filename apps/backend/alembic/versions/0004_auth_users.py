"""auth users

Revision ID: 0004_auth_users
Revises: 0003_equipment_registry
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_auth_users"
down_revision = "0003_equipment_registry"
branch_labels = None
depends_on = None

SCHEMA = "gestione_vse"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "utenti" in inspector.get_table_names(schema=SCHEMA):
        return
    op.create_table(
        "utenti",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("nome", sa.String(255)),
        sa.Column("ruolo", sa.String(50), nullable=False, server_default="admin"),
        sa.Column("attivo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("username", name="uq_utenti_username"),
        schema=SCHEMA,
    )
    op.create_index("ix_utenti_username", "utenti", ["username"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("utenti", schema=SCHEMA)
