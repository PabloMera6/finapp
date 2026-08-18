"""fix transfer_pair_id FK on delete

Antes, transactions.transfer_pair_id -> transactions.id no tenía
ON DELETE definido (NO ACTION por defecto en Postgres). Esto provocaba
un error de foreign key al borrar movimientos que eran la pareja de una
transferencia interna detectada por transfer_detector, porque otra fila
seguía apuntando a la que se intentaba eliminar.

Esta migración recrea la constraint con ON DELETE SET NULL: al borrar
un movimiento, cualquier otro movimiento que lo tuviera como pareja de
transferencia simplemente queda con transfer_pair_id = NULL (y sigue
teniendo is_transfer/is_internal_transfer en su valor anterior, que el
código de aplicación se encarga de recalcular si hace falta).

Revision ID: 1c451625c317
Revises: 7f8a1d71c94f
Create Date: 2026-08-18 00:00:00.000000

"""
from alembic import op


revision = '1c451625c317'
down_revision = '7f8a1d71c94f'
branch_labels = None
depends_on = None


OLD_CONSTRAINT_NAME = "transactions_transfer_pair_id_fkey"
NEW_CONSTRAINT_NAME = "transactions_transfer_pair_id_fkey"


def upgrade():
    op.drop_constraint(OLD_CONSTRAINT_NAME, "transactions", type_="foreignkey")
    op.create_foreign_key(
        NEW_CONSTRAINT_NAME,
        "transactions",
        "transactions",
        ["transfer_pair_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(NEW_CONSTRAINT_NAME, "transactions", type_="foreignkey")
    op.create_foreign_key(
        OLD_CONSTRAINT_NAME,
        "transactions",
        "transactions",
        ["transfer_pair_id"],
        ["id"],
    )
