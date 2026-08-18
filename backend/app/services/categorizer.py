"""
Motor de categorización (secciones 15-16).

Orden de prioridad:
  1. CategoryRule del usuario (aprendidas al corregir categorías), ordenadas
     por prioridad ascendente (menor número = mayor prioridad).
  2. Reglas deterministas por defecto (DEFAULT_MERCHANT_RULES).
  3. Heurísticas por tipo (Bizum -> Bizum, transferencia -> Transferencias,
     inversión -> Inversión...).
  4. "Otros / Sin categorizar" si nada coincide.

No se usa IA para esto. La arquitectura permite añadir un
`LLMCategorizer` opcional más adelante para casos ambiguos, implementando
la misma interfaz `suggest(description) -> (category, subcategory) | None`
y ejecutándose solo tras agotar las reglas deterministas.
"""
from sqlalchemy.orm import Session

from app.categories import DEFAULT_MERCHANT_RULES
from app.models import Category, CategoryRule, Subcategory, Transaction


def _get_or_none(db: Session, model, **filters):
    return db.query(model).filter_by(**filters).first()


def categorize_transaction(db: Session, user_id: str, tx: Transaction) -> None:
    desc_upper = (tx.description or "").upper()

    # 1. Reglas del usuario, por prioridad
    user_rules = (
        db.query(CategoryRule)
        .filter(CategoryRule.user_id == user_id)
        .order_by(CategoryRule.priority.asc())
        .all()
    )
    for rule in user_rules:
        if rule.pattern.upper() in desc_upper:
            tx.category_id = rule.category_id
            tx.subcategory_id = rule.subcategory_id
            return

    # 2. Reglas por defecto
    for pattern, cat_name, subcat_name in DEFAULT_MERCHANT_RULES:
        if pattern in desc_upper:
            category = _get_or_none(db, Category, name=cat_name)
            subcategory = (
                db.query(Subcategory)
                .filter(Subcategory.category_id == category.id, Subcategory.name == subcat_name)
                .first()
                if category else None
            )
            if category:
                tx.category_id = category.id
                tx.subcategory_id = subcategory.id if subcategory else None
                return

    # 3. Heurísticas por tipo
    type_to_category = {
        "TRANSFER": "Transferencias",
        "INVESTMENT_BUY": "Inversión",
        "INVESTMENT_SELL": "Inversión",
        "DIVIDEND": "Inversión",
        "INTEREST": "Inversión",
        "FEE": "Comisiones",
        "INCOME": "Otros",
    }
    if tx.is_bizum:
        category = _get_or_none(db, Category, name="Bizum")
        if category:
            tx.category_id = category.id
            return

    cat_name = type_to_category.get(tx.type.value if hasattr(tx.type, "value") else tx.type)
    if cat_name:
        category = _get_or_none(db, Category, name=cat_name)
        if category:
            tx.category_id = category.id
            return

    # 4. Sin categorizar
    fallback = _get_or_none(db, Category, name="Otros")
    if fallback:
        tx.category_id = fallback.id


def learn_rule_from_correction(
    db: Session, user_id: str, transaction: Transaction, category_id: str, subcategory_id: str | None
) -> None:
    """Crea/actualiza una CategoryRule cuando el usuario corrige manualmente una categoría."""
    pattern = (transaction.merchant or transaction.description or "").strip().upper()[:60]
    if not pattern:
        return
    existing = (
        db.query(CategoryRule)
        .filter(CategoryRule.user_id == user_id, CategoryRule.pattern == pattern)
        .first()
    )
    if existing:
        existing.category_id = category_id
        existing.subcategory_id = subcategory_id
        existing.priority = 10  # las reglas aprendidas del usuario tienen alta prioridad
    else:
        db.add(CategoryRule(
            user_id=user_id,
            pattern=pattern,
            merchant=transaction.merchant,
            category_id=category_id,
            subcategory_id=subcategory_id,
            priority=10,
        ))
    db.commit()
