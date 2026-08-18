import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Account, Transaction, User

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("")
def export_transactions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Exporta todos los movimientos normalizados a CSV (seccion 31)."""
    rows = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == user.id)
        .order_by(Transaction.date.desc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "fecha", "importe", "moneda", "descripcion", "tipo", "cuenta", "entidad",
        "categoria_id", "subcategoria_id", "es_transferencia", "es_bizum",
        "destinatario_bizum", "notas",
    ])
    for t in rows:
        writer.writerow([
            t.date.isoformat(), f"{t.amount:.2f}", t.currency, t.description,
            t.type.value if hasattr(t.type, "value") else t.type,
            t.account_id, t.source, t.category_id or "", t.subcategory_id or "",
            t.is_internal_transfer, t.is_bizum, t.bizum_recipient or "", t.notes or "",
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=movimientos.csv"},
    )
