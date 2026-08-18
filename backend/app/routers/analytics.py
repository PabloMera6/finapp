from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services.analytics_engine import (
    compute_account_breakdown,
    compute_category_breakdown,
    compute_merchant_breakdown,
    compute_month_projection,
    compute_monthly_totals,
    compute_weekday_heatmap,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/comparison")
def compare_months(
    year_a: int, month_a: int, year_b: int, month_b: int,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    totals_a = compute_monthly_totals(db, user.id, year_a, month_a)
    totals_b = compute_monthly_totals(db, user.id, year_b, month_b)

    cats_a = {c["category"]: c["amount"] for c in compute_category_breakdown(db, user.id, year_a, month_a)}
    cats_b = {c["category"]: c["amount"] for c in compute_category_breakdown(db, user.id, year_b, month_b)}

    all_categories = set(cats_a) | set(cats_b)
    rows = []
    for cat in all_categories:
        a = cats_a.get(cat, 0.0)
        b = cats_b.get(cat, 0.0)
        diff = b - a
        pct = (diff / a * 100) if a > 0 else None
        rows.append({"category": cat, "month_a": a, "month_b": b, "diff": round(diff, 2), "pct": round(pct, 1) if pct is not None else None})
    rows.sort(key=lambda r: abs(r["diff"]), reverse=True)

    return {
        "month_a": f"{year_a}-{month_a:02d}",
        "month_b": f"{year_b:04d}-{month_b:02d}",
        "totals_a": {"income": float(totals_a.income), "expenses": float(totals_a.expenses), "savings": float(totals_a.savings), "investment": float(totals_a.investment)},
        "totals_b": {"income": float(totals_b.income), "expenses": float(totals_b.expenses), "savings": float(totals_b.savings), "investment": float(totals_b.investment)},
        "categories": rows,
    }


@router.get("/summary")
def financial_summary(
    year_from: int = Query(..., ge=2000, le=2100),
    month_from: int = Query(..., ge=1, le=12),
    year_to: int = Query(..., ge=2000, le=2100),
    month_to: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    start_key = year_from * 12 + month_from
    end_key = year_to * 12 + month_to
    if start_key > end_key:
        raise HTTPException(status_code=400, detail="El periodo inicial no puede ser posterior al final")
    if end_key - start_key > 120:
        raise HTTPException(status_code=400, detail="El periodo máximo es de 10 años")

    monthly = []
    total_income = total_expenses = total_savings = total_investment = 0.0
    key = start_key
    while key <= end_key:
        y = (key - 1) // 12
        m = (key - 1) % 12 + 1
        t = compute_monthly_totals(db, user.id, y, m)
        row = {
            "month": f"{y}-{m:02d}",
            "income": float(t.income),
            "expenses": float(t.expenses),
            "savings": float(t.savings),
            "investment": float(t.investment),
            "savings_rate": t.savings_rate,
        }
        monthly.append(row)
        total_income += row["income"]
        total_expenses += row["expenses"]
        total_savings += row["savings"]
        total_investment += row["investment"]
        key += 1

    category_totals = {}
    for row in monthly:
        y, m = map(int, row["month"].split("-"))
        for cat in compute_category_breakdown(db, user.id, y, m):
            category_totals[cat["category"]] = category_totals.get(cat["category"], 0.0) + cat["amount"]
    top_categories = sorted(
        [{"category": k, "amount": round(v, 2)} for k, v in category_totals.items()],
        key=lambda x: x["amount"], reverse=True,
    )[:10]

    return {
        "period": {"from": f"{year_from}-{month_from:02d}", "to": f"{year_to}-{month_to:02d}"},
        "totals": {
            "income": round(total_income, 2),
            "expenses": round(total_expenses, 2),
            "savings": round(total_savings, 2),
            "investment": round(total_investment, 2),
            "savings_rate": round(total_savings / total_income, 4) if total_income > 0 else 0,
            "months": len(monthly),
        },
        "monthly": monthly,
        "top_categories": top_categories,
    }


def _validate_range(year_from: int, month_from: int, year_to: int, month_to: int):
    start_key = year_from * 12 + month_from
    end_key = year_to * 12 + month_to
    if start_key > end_key:
        raise HTTPException(status_code=400, detail="El periodo inicial no puede ser posterior al final")
    if end_key - start_key > 120:
        raise HTTPException(status_code=400, detail="El periodo máximo es de 10 años")


@router.get("/merchants")
def top_merchants(
    year_from: int = Query(..., ge=2000, le=2100),
    month_from: int = Query(..., ge=1, le=12),
    year_to: int = Query(..., ge=2000, le=2100),
    month_to: int = Query(..., ge=1, le=12),
    limit: int = Query(default=15, ge=1, le=50),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Comercios/contrapartes en los que más se ha gastado en el periodo, con frecuencia y ticket medio."""
    _validate_range(year_from, month_from, year_to, month_to)
    return {
        "period": {"from": f"{year_from}-{month_from:02d}", "to": f"{year_to}-{month_to:02d}"},
        "merchants": compute_merchant_breakdown(db, user.id, year_from, month_from, year_to, month_to, limit=limit),
    }


@router.get("/by-account")
def by_account(
    year_from: int = Query(..., ge=2000, le=2100),
    month_from: int = Query(..., ge=1, le=12),
    year_to: int = Query(..., ge=2000, le=2100),
    month_to: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Ingresos, gastos, ahorro e inversión desglosados por cuenta en el periodo."""
    _validate_range(year_from, month_from, year_to, month_to)
    return {
        "period": {"from": f"{year_from}-{month_from:02d}", "to": f"{year_to}-{month_to:02d}"},
        "accounts": compute_account_breakdown(db, user.id, year_from, month_from, year_to, month_to),
    }


@router.get("/heatmap")
def weekday_heatmap(
    year_from: int = Query(..., ge=2000, le=2100),
    month_from: int = Query(..., ge=1, le=12),
    year_to: int = Query(..., ge=2000, le=2100),
    month_to: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Gasto total y medio por día de la semana, para detectar patrones de consumo."""
    _validate_range(year_from, month_from, year_to, month_to)
    return {
        "period": {"from": f"{year_from}-{month_from:02d}", "to": f"{year_to}-{month_to:02d}"},
        "weekdays": compute_weekday_heatmap(db, user.id, year_from, month_from, year_to, month_to),
    }


@router.get("/projection")
def month_projection(
    year: int = Query(default=None, ge=2000, le=2100),
    month: int = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """
    Proyección de ingresos/gastos/ahorro de fin de mes según el ritmo diario
    observado hasta la fecha. Por defecto usa el mes en curso.
    """
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month
    return compute_month_projection(db, user.id, year, month)
