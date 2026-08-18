"""
Detección de gastos recurrentes (sección 25).

Método simple y explicable: agrupa gastos por (merchant normalizado, importe
aproximado) y considera recurrente un grupo que aparece en >= 3 meses
distintos de los últimos 6, con importes muy similares (tolerancia 5%).
"""
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Account, Transaction

LOOKBACK_MONTHS = 6
MIN_OCCURRENCES = 3
AMOUNT_TOLERANCE_PCT = Decimal("0.05")


def _merchant_key(tx: Transaction) -> str:
    base = (tx.merchant or tx.description or "").upper().strip()
    return base[:40]


def detect_recurring(db: Session, user_id: str) -> list[dict]:
    since = datetime.utcnow() - timedelta(days=30 * LOOKBACK_MONTHS)
    txs = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == user_id)
        .filter(Transaction.date >= since)
        .filter(Transaction.amount < 0)
        .filter(Transaction.is_internal_transfer.is_(False))
        .filter(Transaction.type != "INVESTMENT_BUY")
        .all()
    )

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for tx in txs:
        groups[_merchant_key(tx)].append(tx)

    recurring = []
    for key, group in groups.items():
        if not key:
            continue
        months = {(t.date.year, t.date.month) for t in group}
        if len(months) < MIN_OCCURRENCES:
            continue
        amounts = [abs(t.amount) for t in group]
        avg = sum(amounts) / len(amounts)
        if avg == 0:
            continue
        consistent = all(abs(a - avg) <= avg * AMOUNT_TOLERANCE_PCT for a in amounts)
        if not consistent:
            continue
        for tx in group:
            tx.is_recurring = True
        recurring.append({
            "merchant": key,
            "average_amount": round(float(avg), 2),
            "occurrences": len(months),
            "last_date": max(t.date for t in group).isoformat(),
        })

    db.commit()
    recurring.sort(key=lambda r: r["average_amount"], reverse=True)
    return recurring
