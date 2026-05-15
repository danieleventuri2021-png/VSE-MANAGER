"""user owned data

Revision ID: 0005_user_owned_data
Revises: 0004_auth_users
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_user_owned_data"
down_revision = "0004_auth_users"
branch_labels = None
depends_on = None

SCHEMA = "gestione_vse"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    def has_column(table: str, column: str) -> bool:
        return column in {item["name"] for item in inspector.get_columns(table, schema=SCHEMA)}

    if not has_column("lavori_vse", "owner_user_id"):
        op.add_column("lavori_vse", sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.utenti.id", ondelete="SET NULL")), schema=SCHEMA)
        op.create_index("ix_lavori_vse_owner_user_id", "lavori_vse", ["owner_user_id"], schema=SCHEMA)
    if not has_column("registro_apparecchiature", "owner_user_id"):
        op.add_column("registro_apparecchiature", sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.utenti.id", ondelete="SET NULL")), schema=SCHEMA)
        op.create_index("ix_registro_apparecchiature_owner_user_id", "registro_apparecchiature", ["owner_user_id"], schema=SCHEMA)

    admin_id = bind.execute(sa.text(f"SELECT id FROM {SCHEMA}.utenti WHERE ruolo = 'admin' ORDER BY id LIMIT 1")).scalar()
    if admin_id:
        bind.execute(sa.text(f"UPDATE {SCHEMA}.lavori_vse SET owner_user_id = :admin_id WHERE owner_user_id IS NULL"), {"admin_id": admin_id})
        bind.execute(sa.text(f"UPDATE {SCHEMA}.registro_apparecchiature SET owner_user_id = :admin_id WHERE owner_user_id IS NULL"), {"admin_id": admin_id})

    try:
        op.drop_constraint("uq_registro_cliente_identificativo", "registro_apparecchiature", schema=SCHEMA, type_="unique")
    except Exception:
        pass
    op.create_unique_constraint("uq_registro_owner_cliente_identificativo", "registro_apparecchiature", ["owner_user_id", "cliente_nome", "identificativo"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_constraint("uq_registro_owner_cliente_identificativo", "registro_apparecchiature", schema=SCHEMA, type_="unique")
    op.create_unique_constraint("uq_registro_cliente_identificativo", "registro_apparecchiature", ["cliente_nome", "identificativo"], schema=SCHEMA)
    op.drop_column("registro_apparecchiature", "owner_user_id", schema=SCHEMA)
    op.drop_column("lavori_vse", "owner_user_id", schema=SCHEMA)
