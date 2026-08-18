"""
InsightGenerator (secciones 24 y 53).

Regla estricta: todo insight debe poder trazarse a números reales
calculados por AnalyticsEngine. No se generan conclusiones subjetivas
ni explicaciones inventadas.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.analytics_engine import compute_category_breakdown, compute_monthly_totals


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def generate_insights(db: Session, user_id: str, year: int, month: int) -> list[dict]:
    insights: list[dict] = []

    current = compute_monthly_totals(db, user_id, year, month)
    py, pm = _prev_month(year, month)
    previous = compute_monthly_totals(db, user_id, py, pm)

    if previous.expenses > 0:
        diff = current.expenses - previous.expenses
        pct = float(diff / previous.expenses) * 100
        if diff > 0:
            insights.append({
                "text": f"Has gastado {abs(diff):.0f} € más que el mes pasado ({pct:+.1f}%).",
                "detail": {"current": float(current.expenses), "previous": float(previous.expenses)},
            })
        elif diff < 0:
            insights.append({
                "text": f"Has gastado {abs(diff):.0f} € menos que el mes pasado ({pct:+.1f}%).",
                "detail": {"current": float(current.expenses), "previous": float(previous.expenses)},
            })

    if previous.income > 0:
        rate_diff = (current.savings_rate - previous.savings_rate) * 100
        if abs(rate_diff) >= 1:
            insights.append({
                "text": (
                    f"Tu tasa de ahorro ha pasado del {previous.savings_rate * 100:.0f}% "
                    f"al {current.savings_rate * 100:.0f}%."
                ),
                "detail": {"current": current.savings_rate, "previous": previous.savings_rate},
            })

    current_breakdown = {c["category"]: c["amount"] for c in compute_category_breakdown(db, user_id, year, month)}
    prev_breakdown = {c["category"]: c["amount"] for c in compute_category_breakdown(db, user_id, py, pm)}

    biggest_increase = None
    for cat, amount in current_breakdown.items():
        prev_amount = prev_breakdown.get(cat, 0.0)
        delta = amount - prev_amount
        if biggest_increase is None or delta > biggest_increase[1]:
            biggest_increase = (cat, delta, prev_amount, amount)

    if biggest_increase and biggest_increase[1] > 0:
        cat, delta, prev_amount, amount = biggest_increase
        pct = (delta / prev_amount * 100) if prev_amount > 0 else None
        pct_text = f" (+{pct:.0f}%)" if pct is not None else ""
        insights.append({
            "text": f"El mayor incremento de gasto ha sido en {cat}: +{delta:.0f} €{pct_text}.",
            "detail": {"category": cat, "previous": prev_amount, "current": amount},
        })

    return insights
