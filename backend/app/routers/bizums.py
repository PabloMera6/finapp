from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Account, BizumContact, Transaction, User
from app.services.categorizer import learn_rule_from_correction

router = APIRouter(prefix="/api/bizums", tags=["bizums"])


class BizumUpdate(BaseModel):
    bizum_recipient: str | None = None
    category_id: str | None = None
    subcategory_id: str | None = None
    notes: str | None = None
    remember_contact: bool = False


@router.get("/unidentified")
def unidentified_bizums(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Sección 18: Bizums enviados/recibidos cuyo destinatario no pudo determinarse
    automáticamente a partir del archivo exportado (bizum_recipient IS NULL).
    """
    rows = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == user.id)
        .filter(Transaction.is_bizum.is_(True))
        .filter(Transaction.bizum_recipient.is_(None))
        .order_by(Transaction.date.desc())
        .all()
    )
    return [{
        "id": t.id,
        "date": t.date.isoformat(),
        "amount": float(t.amount),
        "description": t.description,
        "account_id": t.account_id,
        "bizum_direction": t.bizum_direction.value if t.bizum_direction else None,
        "category_id": t.category_id,
    } for t in rows]


@router.patch("/{transaction_id}")
def update_bizum(
    transaction_id: str, payload: BizumUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """
    Destinatario y categoría son independientes (sección 18): se puede guardar
    solo la categoría sin destinatario, o viceversa.
    """
    tx = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == transaction_id, Account.user_id == user.id, Transaction.is_bizum.is_(True))
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Bizum no encontrado")

    if payload.bizum_recipient is not None:
        tx.bizum_recipient = payload.bizum_recipient.strip() or None
        if payload.remember_contact and tx.bizum_recipient:
            existing = db.query(BizumContact).filter(
                BizumContact.user_id == user.id, BizumContact.display_name == tx.bizum_recipient
            ).first()
            if not existing:
                db.add(BizumContact(user_id=user.id, display_name=tx.bizum_recipient))

    if payload.category_id is not None:
        tx.category_id = payload.category_id
        tx.subcategory_id = payload.subcategory_id
    if payload.notes is not None:
        tx.notes = payload.notes

    db.commit()
    return {"ok": True}


@router.get("/contacts")
def list_contacts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    contacts = db.query(BizumContact).filter(BizumContact.user_id == user.id).all()
    return [{"id": c.id, "display_name": c.display_name} for c in contacts]
