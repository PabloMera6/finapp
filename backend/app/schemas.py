from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    institution: str
    account_name: str
    account_type: Optional[str]
    currency: str
    last_four_digits: Optional[str]


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    account_id: str
    date: datetime
    amount: Decimal
    currency: str
    description: str
    type: str
    merchant: Optional[str]
    counterparty: Optional[str]
    is_transfer: bool
    is_internal_transfer: bool
    is_recurring: bool
    is_bizum: bool
    bizum_direction: Optional[str]
    bizum_recipient: Optional[str]
    category_id: Optional[str]
    subcategory_id: Optional[str]
    notes: Optional[str]
    source: str


class TransactionCreate(BaseModel):
    account_id: str
    date: datetime
    amount: Decimal
    currency: str = "EUR"
    description: str
    type: str = "UNKNOWN"
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    notes: Optional[str] = None
    merchant: Optional[str] = None
    counterparty: Optional[str] = None


class TransactionUpdate(BaseModel):
    category_id: Optional[str] = None
    subcategory_id: Optional[str] = None
    bizum_recipient: Optional[str] = None
    is_internal_transfer: Optional[bool] = None
    notes: Optional[str] = None
    remember_rule: bool = False  # si True, crea/actualiza CategoryRule


class ImportPreviewRow(BaseModel):
    row_index: int
    date: Optional[str]
    description: Optional[str]
    amount: Optional[str]
    detected_type: Optional[str]
    is_duplicate: bool
    error: Optional[str] = None


class ImportPreviewResponse(BaseModel):
    detected_institution: Optional[str]
    total_rows: int
    new_rows: int
    duplicate_rows: int
    error_rows: int
    sample: list[ImportPreviewRow]
    import_token: str  # referencia temporal para confirmar la importación


class ImportConfirmRequest(BaseModel):
    import_token: str
    institution: str
    account_id: Optional[str] = None
    new_account_name: Optional[str] = None


class DashboardSummary(BaseModel):
    month: str
    income: Decimal
    expenses: Decimal
    savings: Decimal
    savings_rate: float
    investment: Decimal
    prev_month_income: Decimal
    prev_month_expenses: Decimal
    prev_month_savings: Decimal
    prev_month_investment: Decimal
