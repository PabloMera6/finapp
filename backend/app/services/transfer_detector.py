"""
Detección de transferencias entre cuentas propias (sección 13).

Heurística inicial (simple y explicable, según sección 26):
  - Dos movimientos de cuentas DEL MISMO USUARIO
  - Importes de signo opuesto y mismo valor absoluto (tolerancia 0.01€)
  - Diferencia de fechas <= TRANSFER_WINDOW_DAYS
  - No emparejados ya con otra transferencia

Al confirmarse, ambos movimientos se marcan is_transfer=True,
is_internal_transfer=True y se enlazan mediante transfer_pair_id.
Esto los excluye de ingresos/gastos reales (ver AnalyticsEngine).
El usuario puede corregir manualmente esta detección (PATCH /transactions/:id).
"""
from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Account, Transaction

TRANSFER_WINDOW_DAYS = 3
AMOUNT_TOLERANCE = Decimal("0.01")


def detect_internal_transfers(db: Session, user_id: str) -> int:
    """Recorre movimientos no emparejados del usuario y empareja candidatos. Devuelve nº de pares creados."""
    candidates = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == user_id)
        .filter(Transaction.transfer_pair_id.is_(None))
        .order_by(Transaction.date)
        .all()
    )

    paired = 0
    used_ids: set[str] = set()

    for tx in candidates:
        if tx.id in used_ids or tx.transfer_pair_id:
            continue
        window_start = tx.date - timedelta(days=TRANSFER_WINDOW_DAYS)
        window_end = tx.date + timedelta(days=TRANSFER_WINDOW_DAYS)

        for other in candidates:
            if other.id == tx.id or other.id in used_ids or other.transfer_pair_id:
                continue
            if other.account_id == tx.account_id:
                continue  # debe ser entre cuentas distintas
            if not (window_start <= other.date <= window_end):
                continue
            if abs(abs(tx.amount) - abs(other.amount)) > AMOUNT_TOLERANCE:
                continue
            if (tx.amount > 0) == (other.amount > 0):
                continue  # deben tener signo opuesto

            tx.is_transfer = True
            tx.is_internal_transfer = True
            tx.transfer_pair_id = other.id
            other.is_transfer = True
            other.is_internal_transfer = True
            other.transfer_pair_id = tx.id

            used_ids.add(tx.id)
            used_ids.add(other.id)
            paired += 1
            break

    db.commit()
    return paired
