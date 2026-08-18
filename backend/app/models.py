"""
Modelo de datos normalizado y correctamente tipado.
Todos los importes usan NUMERIC (Decimal) — nunca float — para evitar
errores de precisión en cálculos financieros (ver sección "Precisión").
"""
import enum
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String,
    Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class TransactionType(str, enum.Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"
    INVESTMENT_BUY = "INVESTMENT_BUY"
    INVESTMENT_SELL = "INVESTMENT_SELL"
    DIVIDEND = "DIVIDEND"
    INTEREST = "INTEREST"
    FEE = "FEE"
    UNKNOWN = "UNKNOWN"


class BizumDirection(str, enum.Enum):
    SENT = "SENT"
    RECEIVED = "RECEIVED"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    category_rules = relationship("CategoryRule", back_populates="user", cascade="all, delete-orphan")
    bizum_contacts = relationship("BizumContact", back_populates="user", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    institution = Column(String, nullable=False)  # imagin | myinvestor | trade_republic
    account_name = Column(String, nullable=False)
    account_type = Column(String, nullable=True)  # checking | investment | cash
    currency = Column(String, default="EUR", nullable=False)
    last_four_digits = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String, unique=True, nullable=False)
    is_system = Column(Boolean, default=True)  # categorías predefinidas vs. creadas por el usuario

    subcategories = relationship("Subcategory", back_populates="category", cascade="all, delete-orphan")


class Subcategory(Base):
    __tablename__ = "subcategories"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    category_id = Column(UUID(as_uuid=False), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)

    category = relationship("Category", back_populates="subcategories")
    __table_args__ = (UniqueConstraint("category_id", "name", name="uq_subcategory_per_category"),)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(UUID(as_uuid=False), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    institution = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    total_rows = Column(Integer, default=0)
    imported_rows = Column(Integer, default=0)
    duplicate_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    status = Column(String, default="completed")  # pending | completed | failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("Transaction", back_populates="import_batch")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    account_id = Column(UUID(as_uuid=False), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String, nullable=True)
    fingerprint = Column(String, nullable=False, index=True)  # deduplicación

    date = Column(DateTime(timezone=True), nullable=False)
    value_date = Column(DateTime(timezone=True), nullable=True)

    amount = Column(Numeric(14, 2), nullable=False)  # NUNCA float
    currency = Column(String, default="EUR", nullable=False)

    description = Column(Text, nullable=False)
    raw_description = Column(Text, nullable=True)

    type = Column(Enum(TransactionType), default=TransactionType.UNKNOWN, nullable=False)

    category_id = Column(UUID(as_uuid=False), ForeignKey("categories.id"), nullable=True)
    subcategory_id = Column(UUID(as_uuid=False), ForeignKey("subcategories.id"), nullable=True)

    merchant = Column(String, nullable=True)
    counterparty = Column(String, nullable=True)

    is_transfer = Column(Boolean, default=False)
    is_internal_transfer = Column(Boolean, default=False)
    transfer_pair_id = Column(
        UUID(as_uuid=False),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_recurring = Column(Boolean, default=False)

    is_bizum = Column(Boolean, default=False)
    bizum_direction = Column(Enum(BizumDirection), nullable=True)
    bizum_recipient = Column(String, nullable=True)  # NULL si no se puede determinar
    bizum_confidence = Column(String, nullable=True)  # low | medium | high

    notes = Column(Text, nullable=True)
    source = Column(String, nullable=False)  # imagin | myinvestor | trade_republic
    import_batch_id = Column(UUID(as_uuid=False), ForeignKey("import_batches.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account = relationship("Account", back_populates="transactions")
    import_batch = relationship("ImportBatch", back_populates="transactions")
    category = relationship("Category")
    subcategory = relationship("Subcategory")

    __table_args__ = (
        UniqueConstraint("account_id", "fingerprint", name="uq_transaction_fingerprint"),
    )


class CategoryRule(Base):
    """Reglas aprendidas de categorización, por usuario, con prioridad."""
    __tablename__ = "category_rules"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pattern = Column(String, nullable=False)  # substring o merchant normalizado
    merchant = Column(String, nullable=True)
    category_id = Column(UUID(as_uuid=False), ForeignKey("categories.id"), nullable=False)
    subcategory_id = Column(UUID(as_uuid=False), ForeignKey("subcategories.id"), nullable=True)
    priority = Column(Integer, default=100)  # menor número = mayor prioridad
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="category_rules")


class BizumContact(Base):
    """Referencia interna opcional para sugerir destinatarios de Bizum repetidos."""
    __tablename__ = "bizum_contacts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    display_name = Column(String, nullable=False)
    match_pattern = Column(String, nullable=True)  # texto que ayuda a sugerir este contacto
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="bizum_contacts")
