from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Account, Transaction, User
from app.schemas import TransactionCreate, TransactionUpdate
from app.services.dedup import compute_fingerprint
from app.parsers.base import NormalizedTransaction
from app.services.categorizer import learn_rule_from_correction

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("")
def list_transactions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    account_id: Optional[str] = None,
    institution: Optional[str] = None,
    category_id: Optional[str] = None,
    tx_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    q = db.query(Transaction).join(Account, Transaction.account_id == Account.id).filter(Account.user_id == user.id)

    if date_from:
        q = q.filter(Transaction.date >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(Transaction.date <= datetime.fromisoformat(date_to))
    if account_id:
        q = q.filter(Transaction.account_id == account_id)
    if institution:
        q = q.filter(Transaction.source == institution)
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if tx_type:
        q = q.filter(Transaction.type == tx_type)
    if search:
        like = f"%{search}%"
        q = q.filter(Transaction.description.ilike(like))

    total = q.count()
    rows = q.order_by(Transaction.date.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [{
            "id": t.id,
            "account_id": t.account_id,
            "date": t.date.isoformat(),
            "amount": float(t.amount),
            "currency": t.currency,
            "description": t.description,
            "type": t.type.value if hasattr(t.type, "value") else t.type,
            "merchant": t.merchant,
            "counterparty": t.counterparty,
            "is_transfer": t.is_transfer,
            "is_internal_transfer": t.is_internal_transfer,
            "is_recurring": t.is_recurring,
            "is_bizum": t.is_bizum,
            "bizum_direction": t.bizum_direction.value if t.bizum_direction else None,
            "bizum_recipient": t.bizum_recipient,
            "category_id": t.category_id,
            "subcategory_id": t.subcategory_id,
            "notes": t.notes,
            "source": t.source,
        } for t in rows],
    }


@router.post("")
def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    account = (
        db.query(Account)
        .filter(Account.id == payload.account_id, Account.user_id == user.id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada")

    try:
        tx_type = payload.type
        from app.models import TransactionType
        tx_enum = TransactionType(tx_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Tipo de movimiento no válido")

    # Normaliza el signo para que la analítica sea consistente.
    amount = payload.amount
    if tx_enum in {TransactionType.EXPENSE, TransactionType.INVESTMENT_BUY, TransactionType.FEE}:
        amount = -abs(amount)
    elif tx_enum in {TransactionType.INCOME, TransactionType.INVESTMENT_SELL, TransactionType.DIVIDEND, TransactionType.INTEREST}:
        amount = abs(amount)

    normalized = NormalizedTransaction(
        date=payload.date,
        value_date=None,
        amount=amount,
        currency=payload.currency,
        description=payload.description.strip(),
        raw_description=payload.description.strip(),
        source=account.institution,
        type=tx_enum.value,
    )
    fingerprint = compute_fingerprint(account.id, normalized)

    tx = Transaction(
        account_id=account.id,
        date=payload.date,
        amount=amount,
        currency=payload.currency,
        description=payload.description.strip(),
        raw_description=payload.description.strip(),
        type=tx_enum,
        category_id=payload.category_id,
        subcategory_id=payload.subcategory_id,
        notes=payload.notes,
        merchant=payload.merchant,
        counterparty=payload.counterparty,
        source=account.institution,
        fingerprint=fingerprint,
    )
    db.add(tx)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        if "uq_transaction_fingerprint" in str(exc):
            raise HTTPException(status_code=409, detail="Ya existe un movimiento igual")
        raise
    db.refresh(tx)
    return {"id": tx.id, "ok": True}

@router.patch("/{transaction_id}")
def update_transaction(
    transaction_id: str,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tx = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == transaction_id, Account.user_id == user.id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    if payload.category_id is not None:
        tx.category_id = payload.category_id
    if payload.subcategory_id is not None:
        tx.subcategory_id = payload.subcategory_id
    if payload.bizum_recipient is not None:
        tx.bizum_recipient = payload.bizum_recipient
    if payload.is_internal_transfer is not None:
        tx.is_internal_transfer = payload.is_internal_transfer
        tx.is_transfer = payload.is_internal_transfer
    if payload.notes is not None:
        tx.notes = payload.notes

    if payload.remember_rule and payload.category_id:
        learn_rule_from_correction(db, user.id, tx, payload.category_id, payload.subcategory_id)

    db.commit()
    return {"ok": True}


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tx = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == transaction_id, Account.user_id == user.id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    # Si este movimiento es la pareja de una transferencia interna, hay que
    # romper esa referencia antes de borrar (mismo motivo que en
    # accounts.py: transfer_pair_id apunta a otra fila de "transactions").
    db.query(Transaction).filter(Transaction.transfer_pair_id == tx.id).update(
        {Transaction.transfer_pair_id: None},
        synchronize_session=False,
    )

    db.delete(tx)
    db.commit()
    return {"ok": True}
