"""
Tests de regresión para el borrado de movimientos/cuentas cuando existen
transferencias internas enlazadas mediante transfer_pair_id.

Bug original: al borrar los movimientos de una cuenta (o la cuenta entera),
si alguno de esos movimientos era la pareja de una transferencia interna
detectada por transfer_detector, el borrado fallaba con un error de
integridad referencial (foreign key), porque transfer_pair_id no tenía
ON DELETE definido y, además, el router tenía dos endpoints duplicados en
la misma ruta DELETE /{account_id}/transactions: el primero (que se
ejecutaba de verdad, por orden de registro en FastAPI) no rompía esa
referencia antes de borrar.
"""
from datetime import datetime
from decimal import Decimal

from app.models import Account, ImportBatch, Transaction, TransactionType
from app.routers.accounts import delete_account, delete_account_transactions
from app.services.dedup import compute_fingerprint
from app.parsers.base import NormalizedTransaction


def _make_account(db, user, institution="imagin", name="cuenta test"):
    acc = Account(user_id=user.id, institution=institution, account_name=name, currency="EUR")
    db.add(acc)
    db.flush()
    return acc


def _make_transaction(db, account, amount, date, description="mov", tx_type="TRANSFER"):
    norm = NormalizedTransaction(
        date=date, amount=amount, currency="EUR", description=description,
        raw_description=description, source=account.institution, type=tx_type,
    )
    fp = compute_fingerprint(account.id, norm)
    tx = Transaction(
        account_id=account.id, fingerprint=fp, date=date, amount=amount, currency="EUR",
        description=description, raw_description=description, type=TransactionType(tx_type),
        source=account.institution,
    )
    db.add(tx)
    db.flush()
    return tx


def _link_as_transfer_pair(db, tx_a, tx_b):
    tx_a.is_transfer = True
    tx_a.is_internal_transfer = True
    tx_a.transfer_pair_id = tx_b.id
    tx_b.is_transfer = True
    tx_b.is_internal_transfer = True
    tx_b.transfer_pair_id = tx_a.id
    db.flush()


def test_delete_account_transactions_with_cross_account_transfer_pair(db_session, test_user):
    """
    Borrar los movimientos de la cuenta A no debe fallar aunque uno de ellos
    sea la pareja (transfer_pair_id) de un movimiento que sigue vivo en la
    cuenta B. La cuenta B debe conservar su movimiento, con
    transfer_pair_id = None tras el borrado.
    """
    acc_a = _make_account(db_session, test_user, "imagin", "Corriente")
    acc_b = _make_account(db_session, test_user, "myinvestor", "Ahorro")

    tx_out = _make_transaction(db_session, acc_a, Decimal("-500.00"), datetime(2026, 7, 10), "TRANSFERENCIA A AHORRO")
    tx_in = _make_transaction(db_session, acc_b, Decimal("500.00"), datetime(2026, 7, 11), "TRASPASO DESDE CORRIENTE")
    _link_as_transfer_pair(db_session, tx_out, tx_in)
    db_session.commit()

    result = delete_account_transactions(
        account_id=acc_a.id, db=db_session, user=test_user,
    )

    assert result["ok"] is True
    assert result["deleted_count"] == 1

    remaining = db_session.query(Transaction).filter(Transaction.account_id == acc_b.id).all()
    assert len(remaining) == 1
    assert remaining[0].id == tx_in.id
    assert remaining[0].transfer_pair_id is None

    assert db_session.query(Transaction).filter(Transaction.account_id == acc_a.id).count() == 0


def test_delete_account_removes_account_and_handles_transfer_pair(db_session, test_user):
    """delete_account borra la cuenta entera, sus movimientos y sus import batches,
    y rompe correctamente las referencias transfer_pair_id hacia otras cuentas."""
    acc_a = _make_account(db_session, test_user, "imagin", "Corriente 2")
    acc_b = _make_account(db_session, test_user, "myinvestor", "Ahorro 2")

    tx_out = _make_transaction(db_session, acc_a, Decimal("-200.00"), datetime(2026, 7, 1), "SALIDA")
    tx_in = _make_transaction(db_session, acc_b, Decimal("200.00"), datetime(2026, 7, 2), "ENTRADA")
    _link_as_transfer_pair(db_session, tx_out, tx_in)

    batch = ImportBatch(
        user_id=test_user.id, account_id=acc_a.id, institution="imagin",
        filename="extracto.csv", total_rows=1, imported_rows=1,
    )
    db_session.add(batch)
    db_session.commit()

    result = delete_account(account_id=acc_a.id, db=db_session, user=test_user)

    assert result["ok"] is True
    assert result["deleted_transactions"] == 1
    assert result["deleted_import_batches"] == 1

    assert db_session.query(Account).filter(Account.id == acc_a.id).first() is None
    assert db_session.query(ImportBatch).filter(ImportBatch.account_id == acc_a.id).count() == 0

    remaining_tx = db_session.query(Transaction).filter(Transaction.account_id == acc_b.id).first()
    assert remaining_tx is not None
    assert remaining_tx.transfer_pair_id is None


def test_delete_account_transactions_without_transfers_still_works(db_session, test_user):
    """Caso simple sin transferencias: sigue funcionando como antes."""
    acc = _make_account(db_session, test_user, "imagin", "Solo gastos")
    _make_transaction(db_session, acc, Decimal("-10.00"), datetime(2026, 7, 1), "compra", "EXPENSE")
    _make_transaction(db_session, acc, Decimal("-20.00"), datetime(2026, 7, 2), "compra 2", "EXPENSE")
    db_session.commit()

    result = delete_account_transactions(account_id=acc.id, db=db_session, user=test_user)

    assert result["deleted_count"] == 2
    assert db_session.query(Transaction).filter(Transaction.account_id == acc.id).count() == 0
