from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.analytics_engine import compute_category_breakdown, compute_monthly_totals

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


@router.get("")
def dashboard_summary(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    current = compute_monthly_totals(db, user.id, year, month)
    py, pm = _prev_month(year, month)
    previous = compute_monthly_totals(db, user.id, py, pm)

    return {
        "month": f"{year}-{month:02d}",
        "income": float(current.income),
        "expenses": float(current.expenses),
        "savings": float(current.savings),
        "savings_rate": current.savings_rate,
        "investment": float(current.investment),
        "prev_month": {
            "income": float(previous.income),
            "expenses": float(previous.expenses),
            "savings": float(previous.savings),
            "investment": float(previous.investment),
        },
        "category_breakdown": compute_category_breakdown(db, user.id, year, month),
    }


@router.get("/timeseries")
def dashboard_timeseries(
    months: int = Query(default=12, le=36),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serie temporal de ingresos/gastos/ahorro/inversión para gráficos de evolución."""
    now = datetime.utcnow()
    year, month = now.year, now.month
    series = []
    for _ in range(months):
        totals = compute_monthly_totals(db, user.id, year, month)
        series.append({
            "month": f"{year}-{month:02d}",
            "income": float(totals.income),
            "expenses": float(totals.expenses),
            "savings": float(totals.savings),
            "savings_rate": totals.savings_rate,
            "investment": float(totals.investment),
        })
        year, month = _prev_month(year, month)
    series.reverse()
    return series
