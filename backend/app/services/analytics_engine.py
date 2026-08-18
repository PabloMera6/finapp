"""
AnalyticsEngine: cálculos financieros centrales (sección 47).

Reglas (documentadas y aplicadas de forma consistente en todo el sistema):
  Ingresos  = sum(amount > 0) EXCLUYENDO transferencias internas
  Gastos    = sum(amount < 0) EXCLUYENDO transferencias internas
              Y EXCLUYENDO inversión (compra de activos)
  Ahorro    = Ingresos - Gastos
  Inversión = suma de movimientos INVESTMENT_BUY (en valor absoluto)

Todos los importes se manejan como Decimal en todo el pipeline.
"""
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Account, Transaction

EXCLUDED_FROM_EXPENSE_TYPES = {"INVESTMENT_BUY", "TRANSFER", "FEE"}
# Las comisiones SÍ se consideran gasto real en este cálculo por defecto,
# así que las excluimos de EXCLUDED_FROM_EXPENSE_TYPES en la práctica:
EXCLUDED_FROM_EXPENSE_TYPES = {"INVESTMENT_BUY", "TRANSFER"}


@dataclass
class MonthlyTotals:
    income: Decimal
    expenses: Decimal
    savings: Decimal
    savings_rate: float
    investment: Decimal


def _month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    last_day = monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


def compute_monthly_totals(db: Session, user_id: str, year: int, month: int) -> MonthlyTotals:
    start, end = _month_bounds(year, month)
    txs = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == user_id)
        .filter(Transaction.date >= start, Transaction.date <= end)
        .all()
    )

    income = Decimal("0")
    expenses = Decimal("0")
    investment = Decimal("0")

    for tx in txs:
        if tx.is_internal_transfer:
            continue
        tx_type = tx.type.value if hasattr(tx.type, "value") else tx.type
        if tx_type == "INVESTMENT_BUY":
            investment += abs(tx.amount)
            continue
        if tx_type in EXCLUDED_FROM_EXPENSE_TYPES:
            continue
        if tx.amount > 0:
            income += tx.amount
        elif tx.amount < 0:
            expenses += abs(tx.amount)

    savings = income - expenses
    savings_rate = float(savings / income) if income > 0 else 0.0

    return MonthlyTotals(
        income=income, expenses=expenses, savings=savings,
        savings_rate=round(savings_rate, 4), investment=investment,
    )


def compute_category_breakdown(db: Session, user_id: str, year: int, month: int) -> list[dict]:
    start, end = _month_bounds(year, month)
    txs = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == user_id)
        .filter(Transaction.date >= start, Transaction.date <= end)
        .filter(Transaction.amount < 0)
        .filter(Transaction.is_internal_transfer.is_(False))
        .filter(Transaction.type != "INVESTMENT_BUY")
        .all()
    )
    totals: dict[str, Decimal] = {}
    for tx in txs:
        name = tx.category.name if tx.category else "Sin categorizar"
        totals[name] = totals.get(name, Decimal("0")) + abs(tx.amount)

    total_sum = sum(totals.values()) or Decimal("1")
    result = [
        {"category": name, "amount": float(amount), "percentage": round(float(amount / total_sum) * 100, 1)}
        for name, amount in totals.items()
    ]
    result.sort(key=lambda r: r["amount"], reverse=True)
    return result


def _expense_query(db: Session, user_id: str, start: datetime, end: datetime):
    """Query base de gastos reales (excluye transferencias internas e inversión)."""
    return (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == user_id)
        .filter(Transaction.date >= start, Transaction.date <= end)
        .filter(Transaction.amount < 0)
        .filter(Transaction.is_internal_transfer.is_(False))
        .filter(Transaction.type != "INVESTMENT_BUY")
    )


def compute_merchant_breakdown(
    db: Session, user_id: str, year_from: int, month_from: int, year_to: int, month_to: int, limit: int = 15,
) -> list[dict]:
    """Top comercios/contrapartes por gasto acumulado en el periodo, con nº de operaciones y ticket medio."""
    start, _ = _month_bounds(year_from, month_from)
    _, end = _month_bounds(year_to, month_to)

    txs = _expense_query(db, user_id, start, end).all()

    groups: dict[str, list[Transaction]] = defaultdict(list)
    for tx in txs:
        name = (tx.merchant or tx.description or "Desconocido").strip()
        groups[name].append(tx)

    result = []
    for name, group in groups.items():
        total = sum(abs(t.amount) for t in group)
        result.append({
            "merchant": name,
            "total": float(total),
            "transaction_count": len(group),
            "average_amount": float(total / len(group)),
            "last_date": max(t.date for t in group).isoformat(),
        })

    result.sort(key=lambda r: r["total"], reverse=True)
    return result[:limit]


def compute_account_breakdown(
    db: Session, user_id: str, year_from: int, month_from: int, year_to: int, month_to: int,
) -> list[dict]:
    """Ingresos, gastos y ahorro por cuenta en el periodo, para comparar dónde se concentra cada cosa."""
    start, _ = _month_bounds(year_from, month_from)
    _, end = _month_bounds(year_to, month_to)

    accounts = db.query(Account).filter(Account.user_id == user_id).all()

    result = []
    for acc in accounts:
        txs = (
            db.query(Transaction)
            .filter(Transaction.account_id == acc.id)
            .filter(Transaction.date >= start, Transaction.date <= end)
            .all()
        )
        income = Decimal("0")
        expenses = Decimal("0")
        investment = Decimal("0")
        for tx in txs:
            if tx.is_internal_transfer:
                continue
            tx_type = tx.type.value if hasattr(tx.type, "value") else tx.type
            if tx_type == "INVESTMENT_BUY":
                investment += abs(tx.amount)
                continue
            if tx.amount > 0:
                income += tx.amount
            elif tx.amount < 0:
                expenses += abs(tx.amount)

        result.append({
            "account_id": acc.id,
            "account_name": acc.account_name,
            "institution": acc.institution,
            "income": float(income),
            "expenses": float(expenses),
            "savings": float(income - expenses),
            "investment": float(investment),
            "transaction_count": len(txs),
        })

    result.sort(key=lambda r: r["expenses"], reverse=True)
    return result


def compute_weekday_heatmap(
    db: Session, user_id: str, year_from: int, month_from: int, year_to: int, month_to: int,
) -> list[dict]:
    """Gasto medio y total por día de la semana, para detectar patrones (p.ej. gasto alto los viernes)."""
    start, _ = _month_bounds(year_from, month_from)
    _, end = _month_bounds(year_to, month_to)

    txs = _expense_query(db, user_id, start, end).all()

    WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    totals = {i: Decimal("0") for i in range(7)}
    counts = {i: 0 for i in range(7)}

    for tx in txs:
        wd = tx.date.weekday()
        totals[wd] += abs(tx.amount)
        counts[wd] += 1

    result = []
    for i, label in enumerate(WEEKDAYS):
        total = totals[i]
        count = counts[i]
        result.append({
            "weekday": label,
            "total": float(total),
            "transaction_count": count,
            "average_amount": float(total / count) if count else 0.0,
        })
    return result


def compute_month_projection(db: Session, user_id: str, year: int, month: int) -> dict:
    """
    Proyecta ingresos/gastos/ahorro de fin de mes a partir del ritmo diario
    observado hasta hoy (o hasta el último día del mes si ya ha terminado).

    Método simple y explicable: gasto_proyectado = gasto_hasta_hoy / dias_transcurridos * dias_totales_mes.
    No se usan modelos predictivos ni se extrapolan tendencias; es una regla de tres.
    """
    start, end = _month_bounds(year, month)
    last_day = monthrange(year, month)[1]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    is_current_month = (now.year, now.month) == (year, month)
    days_elapsed = now.day if is_current_month else last_day
    days_elapsed = max(1, min(days_elapsed, last_day))

    cutoff = datetime(year, month, days_elapsed, 23, 59, 59)
    effective_end = min(end, cutoff)

    totals_so_far = compute_monthly_totals(db, user_id, year, month)
    # Recalculamos limitando la ventana a lo transcurrido, en vez de reutilizar
    # compute_monthly_totals (que cubre el mes completo).
    txs = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == user_id)
        .filter(Transaction.date >= start, Transaction.date <= effective_end)
        .all()
    )

    income_so_far = Decimal("0")
    expenses_so_far = Decimal("0")
    for tx in txs:
        if tx.is_internal_transfer:
            continue
        tx_type = tx.type.value if hasattr(tx.type, "value") else tx.type
        if tx_type == "INVESTMENT_BUY":
            continue
        if tx.amount > 0:
            income_so_far += tx.amount
        elif tx.amount < 0:
            expenses_so_far += abs(tx.amount)

    ratio = Decimal(last_day) / Decimal(days_elapsed)
    projected_income = income_so_far * ratio
    projected_expenses = expenses_so_far * ratio
    projected_savings = projected_income - projected_expenses

    return {
        "month": f"{year}-{month:02d}",
        "days_elapsed": days_elapsed,
        "days_total": last_day,
        "income_so_far": float(income_so_far),
        "expenses_so_far": float(expenses_so_far),
        "projected_income": round(float(projected_income), 2),
        "projected_expenses": round(float(projected_expenses), 2),
        "projected_savings": round(float(projected_savings), 2),
        "is_current_month": is_current_month,
    }
