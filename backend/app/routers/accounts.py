from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Account, ImportBatch, Transaction, User

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("")
def list_accounts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    accounts = db.query(Account).filter(Account.user_id == user.id).all()

    result = []

    for acc in accounts:
        tx_count = (
            db.query(func.count(Transaction.id))
            .filter(Transaction.account_id == acc.id)
            .scalar()
        )

        balance = (
            db.query(func.sum(Transaction.amount))
            .filter(Transaction.account_id == acc.id)
            .scalar()
        )

        last_import = (
            db.query(ImportBatch)
            .filter(ImportBatch.account_id == acc.id)
            .order_by(ImportBatch.created_at.desc())
            .first()
        )

        result.append({
            "id": acc.id,
            "institution": acc.institution,
            "account_name": acc.account_name,
            "account_type": acc.account_type,
            "currency": acc.currency,
            "last_four_digits": acc.last_four_digits,
            "transaction_count": tx_count or 0,
            "calculated_balance": float(balance) if balance is not None else None,
            "last_import_at": (
                last_import.created_at.isoformat()
                if last_import
                else None
            ),
        })

    return result


@router.delete("/{account_id}/transactions")
def delete_account_transactions(
    account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Elimina todos los movimientos y las importaciones asociadas
    a una cuenta, pero conserva la cuenta.

    Antes de eliminar los movimientos se eliminan las referencias
    internas transfer_pair_id para evitar errores de ForeignKey.
    """

    account = (
        db.query(Account)
        .filter(
            Account.id == account_id,
            Account.user_id == user.id,
        )
        .first()
    )

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Cuenta no encontrada",
        )

    # 1. Obtener los IDs de los movimientos de esta cuenta
    transaction_ids = [
        row[0]
        for row in (
            db.query(Transaction.id)
            .filter(Transaction.account_id == account.id)
            .all()
        )
    ]

    deleted_transactions = len(transaction_ids)

    if transaction_ids:
        # 2. Romper las relaciones entre movimientos.
        #
        # Esto es necesario porque transfer_pair_id apunta
        # a otra fila de la misma tabla transactions.
        (
            db.query(Transaction)
            .filter(Transaction.transfer_pair_id.in_(transaction_ids))
            .update(
                {
                    Transaction.transfer_pair_id: None,
                },
                synchronize_session=False,
            )
        )

        # 3. Borrar los movimientos de la cuenta
        (
            db.query(Transaction)
            .filter(Transaction.id.in_(transaction_ids))
            .delete(
                synchronize_session=False,
            )
        )

    # 4. Borrar los registros de importación de la cuenta
    deleted_import_batches = (
        db.query(ImportBatch)
        .filter(ImportBatch.account_id == account.id)
        .delete(
            synchronize_session=False,
        )
    )

    db.commit()

    return {
        "ok": True,
        "deleted_count": deleted_transactions,
        "deleted_import_batches": deleted_import_batches,
    }


@router.delete("/{account_id}")
def delete_account(
    account_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Elimina una cuenta por completo, junto con todos sus movimientos
    e importaciones asociadas.

    Igual que en delete_account_transactions, primero se rompen las
    referencias transfer_pair_id que otras cuentas del usuario puedan
    tener hacia movimientos de esta cuenta (una transferencia interna
    puede enlazar movimientos de dos cuentas distintas). Esto es una
    salvaguarda adicional: la FK ya tiene ON DELETE SET NULL a nivel
    de base de datos, pero lo hacemos explícito aquí para no depender
    silenciosamente de ese comportamiento y para que el borrado sea
    igual de seguro aunque la migración no se hubiera aplicado.
    """

    account = (
        db.query(Account)
        .filter(
            Account.id == account_id,
            Account.user_id == user.id,
        )
        .first()
    )

    if not account:
        raise HTTPException(
            status_code=404,
            detail="Cuenta no encontrada",
        )

    transaction_ids = [
        row[0]
        for row in (
            db.query(Transaction.id)
            .filter(Transaction.account_id == account.id)
            .all()
        )
    ]

    deleted_transactions = len(transaction_ids)

    if transaction_ids:
        (
            db.query(Transaction)
            .filter(Transaction.transfer_pair_id.in_(transaction_ids))
            .update(
                {Transaction.transfer_pair_id: None},
                synchronize_session=False,
            )
        )

        (
            db.query(Transaction)
            .filter(Transaction.id.in_(transaction_ids))
            .delete(synchronize_session=False)
        )

    deleted_import_batches = (
        db.query(ImportBatch)
        .filter(ImportBatch.account_id == account.id)
        .delete(synchronize_session=False)
    )

    account_name = account.account_name
    db.delete(account)
    db.commit()

    return {
        "ok": True,
        "account_name": account_name,
        "deleted_transactions": deleted_transactions,
        "deleted_import_batches": deleted_import_batches,
    }