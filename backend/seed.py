"""
Script de inicialización.

Uso:
  python seed.py            # crea categorías por defecto + usuario admin (desde .env)
  python seed.py --demo     # además carga datos DEMO completamente ficticios
                             # en una cuenta de demostración separada.

El modo demo nunca se mezcla con datos reales: usa un usuario/cuentas
propios marcados explícitamente como demo en el nombre de cuenta.
"""
import sys
from decimal import Decimal
from datetime import datetime, timedelta

from app.categories import DEFAULT_CATEGORIES
from app.config import get_settings
from app.database import SessionLocal
from app.models import Account, Category, Subcategory, Transaction, TransactionType, User
from app.security import hash_password
from app.services.categorizer import categorize_transaction
from app.services.dedup import compute_fingerprint
from app.services.transfer_detector import detect_internal_transfers
from app.parsers.base import NormalizedTransaction

settings = get_settings()


def seed_categories(db):
    for cat_name, subs in DEFAULT_CATEGORIES.items():
        category = db.query(Category).filter(Category.name == cat_name).first()
        if not category:
            category = Category(name=cat_name, is_system=True)
            db.add(category)
            db.flush()
        for sub_name in subs:
            exists = db.query(Subcategory).filter(
                Subcategory.category_id == category.id, Subcategory.name == sub_name
            ).first()
            if not exists:
                db.add(Subcategory(category_id=category.id, name=sub_name))
    db.commit()
    print("Categorías por defecto creadas/actualizadas.")


def seed_admin_user(db):
    user = db.query(User).filter(User.email == settings.admin_email).first()
    if user:
        print(f"Usuario admin ya existe: {settings.admin_email}")
        return user
    user = User(email=settings.admin_email, password_hash=hash_password(settings.admin_password))
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"Usuario admin creado: {settings.admin_email}")
    return user


def seed_demo_data(db, user):
    imagin_acc = Account(user_id=user.id, institution="imagin", account_name="[DEMO] imagin corriente", account_type="checking", currency="EUR")
    ti_acc = Account(user_id=user.id, institution="myinvestor", account_name="[DEMO] MyInvestor", account_type="investment", currency="EUR")
    tr_acc = Account(user_id=user.id, institution="trade_republic", account_name="[DEMO] Trade Republic", account_type="investment", currency="EUR")
    db.add_all([imagin_acc, ti_acc, tr_acc])
    db.flush()

    today = datetime.utcnow()
    demo_rows = [
        (imagin_acc, -6, "NOMINA EMPRESA DEMO SL", Decimal("2100.00"), "INCOME"),
        (imagin_acc, -5, "MERCADONA", Decimal("-64.30"), "EXPENSE"),
        (imagin_acc, -5, "BIZUM A Juan", Decimal("-25.00"), "EXPENSE"),
        (imagin_acc, -4, "BIZUM", Decimal("-15.00"), "EXPENSE"),
        (imagin_acc, -3, "NETFLIX", Decimal("-12.99"), "EXPENSE"),
        (imagin_acc, -3, "SPOTIFY", Decimal("-10.99"), "EXPENSE"),
        (imagin_acc, -2, "RESTAURANTE DEMO", Decimal("-38.50"), "EXPENSE"),
        (imagin_acc, -1, "TRANSFERENCIA A MYINVESTOR", Decimal("-500.00"), "TRANSFER"),
        (ti_acc, -1, "TRASPASO DESDE IMAGIN", Decimal("500.00"), "TRANSFER"),
        (ti_acc, -20, "COMPRA FONDO INDEXADO", Decimal("-300.00"), "INVESTMENT_BUY"),
        (tr_acc, -15, "DIVIDEND ISIN DEMO", Decimal("4.20"), "DIVIDEND"),
        (tr_acc, -10, "BUY ISIN DEMO ETF", Decimal("-150.00"), "INVESTMENT_BUY"),
    ]

    for account, days_ago, desc, amount, tx_type in demo_rows:
        date = today - timedelta(days=days_ago)
        norm = NormalizedTransaction(
            date=date, amount=amount, currency="EUR", description=desc, raw_description=desc,
            source=account.institution, type=tx_type,
            is_bizum="BIZUM" in desc.upper(),
        )
        fp = compute_fingerprint(account.id, norm)
        db_tx = Transaction(
            account_id=account.id, fingerprint=fp, date=date, amount=amount, currency="EUR",
            description=desc, raw_description=desc, type=TransactionType(tx_type),
            is_bizum=norm.is_bizum, source=account.institution,
        )
        db.add(db_tx)
        db.flush()
        categorize_transaction(db, user.id, db_tx)

    db.commit()
    detect_internal_transfers(db, user.id)
    print("Datos DEMO cargados (ficticios, no reales).")


def main():
    db = SessionLocal()
    try:
        seed_categories(db)
        user = seed_admin_user(db)
        if "--demo" in sys.argv:
            seed_demo_data(db, user)
    finally:
        db.close()


if __name__ == "__main__":
    main()
