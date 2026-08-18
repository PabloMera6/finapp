from datetime import datetime
from decimal import Decimal

from app.models import Account, Category, CategoryRule, Transaction, TransactionType
from app.services.categorizer import categorize_transaction, learn_rule_from_correction
from app.services.dedup import compute_fingerprint
from app.services.transfer_detector import detect_internal_transfers
from app.parsers.base import NormalizedTransaction


def _make_account(db, user, institution="imagin", name="cuenta test"):
    acc = Account(user_id=user.id, institution=institution, account_name=name, currency="EUR")
    db.add(acc)
    db.flush()
    return acc


def _make_transaction(db, account, amount, date, description="mov", tx_type="EXPENSE"):
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


def test_transfer_detection_pairs_opposite_amounts(db_session, test_user):
    acc_a = _make_account(db_session, test_user, "imagin", "imagin test")
    acc_b = _make_account(db_session, test_user, "myinvestor", "myinvestor test")

    tx_out = _make_transaction(db_session, acc_a, Decimal("-500.00"), datetime(2026, 7, 10), "TRANSFERENCIA A MYINVESTOR", "TRANSFER")
    tx_in = _make_transaction(db_session, acc_b, Decimal("500.00"), datetime(2026, 7, 11), "TRASPASO DESDE IMAGIN", "TRANSFER")
    db_session.commit()

    pairs = detect_internal_transfers(db_session, test_user.id)
    db_session.refresh(tx_out)
    db_session.refresh(tx_in)

    assert pairs == 1
    assert tx_out.is_internal_transfer is True
    assert tx_in.is_internal_transfer is True
    assert tx_out.transfer_pair_id == tx_in.id


def test_transfer_detection_does_not_pair_same_account(db_session, test_user):
    acc_a = _make_account(db_session, test_user, "imagin", "imagin test 2")
    tx1 = _make_transaction(db_session, acc_a, Decimal("-100.00"), datetime(2026, 7, 10), "salida", "EXPENSE")
    tx2 = _make_transaction(db_session, acc_a, Decimal("100.00"), datetime(2026, 7, 10), "entrada", "INCOME")
    db_session.commit()

    pairs = detect_internal_transfers(db_session, test_user.id)
    db_session.refresh(tx1)
    assert tx1.is_internal_transfer is False  # misma cuenta -> no es transferencia interna


def test_categorizer_applies_default_merchant_rule(db_session, test_user):
    acc = _make_account(db_session, test_user, "imagin", "imagin cat test")
    tx = _make_transaction(db_session, acc, Decimal("-20.00"), datetime(2026, 7, 1), "MERCADONA MADRID CENTRO", "EXPENSE")
    db_session.commit()

    categorize_transaction(db_session, test_user.id, tx)
    db_session.commit()

    category = db_session.query(Category).filter(Category.id == tx.category_id).first()
    assert category is not None
    assert category.name == "Alimentación"


def test_user_rule_takes_priority_over_default(db_session, test_user):
    acc = _make_account(db_session, test_user, "imagin", "imagin rule test")
    tx = _make_transaction(db_session, acc, Decimal("-15.00"), datetime(2026, 7, 1), "RESTAURANTE XYZ", "EXPENSE")
    db_session.commit()

    restaurantes = db_session.query(Category).filter(Category.name == "Restaurantes").first()
    learn_rule_from_correction(db_session, test_user.id, tx, restaurantes.id, None)

    tx2 = _make_transaction(db_session, acc, Decimal("-18.00"), datetime(2026, 7, 5), "RESTAURANTE XYZ", "EXPENSE")
    db_session.commit()
    categorize_transaction(db_session, test_user.id, tx2)
    db_session.commit()

    assert tx2.category_id == restaurantes.id
