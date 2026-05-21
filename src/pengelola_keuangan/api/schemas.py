"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Register a new user with email + password."""

    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    first_name: str | None = Field(default=None, max_length=128)


class LoginRequest(BaseModel):
    """Login with email + password."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT bearer token response."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Current user info."""

    id: int
    email: str | None
    first_name: str | None
    username: str | None
    timezone: str
    currency: str
    telegram_linked: bool
    low_balance_threshold: Decimal
    is_admin: bool = False
    profile_mode: Literal["standar", "pengusaha"] = "standar"


class UpdateUserRequest(BaseModel):
    """Update profile fields."""

    first_name: str | None = Field(default=None, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    low_balance_threshold: Decimal | None = Field(default=None, ge=0)
    profile_mode: Literal["standar", "pengusaha"] | None = None


class CategoryResponse(BaseModel):
    """A user category."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    emoji: str | None
    is_default: bool


class CategoryCreate(BaseModel):
    """Create a new category."""

    name: str = Field(min_length=1, max_length=64)
    type: str = Field(pattern="^(in|out)$")
    emoji: str | None = Field(default=None, max_length=8)


class CategoryUpdate(BaseModel):
    """Rename a category."""

    name: str = Field(min_length=1, max_length=64)


class TransactionItemInput(BaseModel):
    """A single line item when creating a transaction."""

    name: str = Field(min_length=1, max_length=255)
    qty: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    subtotal: Decimal = Field(ge=0)


class TransactionItemResponse(BaseModel):
    """A line item on a transaction."""

    id: int
    name: str
    qty: Decimal
    unit_price: Decimal | None
    subtotal: Decimal


class TransactionCreate(BaseModel):
    """Create a new transaction."""

    type: str = Field(pattern="^(in|out)$")
    amount: Decimal = Field(gt=0)
    category_id: int | None = None
    note: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None
    items: list[TransactionItemInput] = Field(default_factory=list)


class TransactionUpdate(BaseModel):
    """Update fields of an existing transaction."""

    amount: Decimal | None = Field(default=None, gt=0)
    category_id: int | None = None
    note: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None
    items: list[TransactionItemInput] | None = None


class TransactionResponse(BaseModel):
    """A transaction row."""

    id: int
    type: str
    amount: Decimal
    category_id: int | None
    category_name: str | None
    note: str | None
    occurred_at: datetime
    items: list[TransactionItemResponse] = Field(default_factory=list)


class CategoryTotalResponse(BaseModel):
    """Per-category totals."""

    category_id: int | None
    category_name: str
    total: Decimal


class MonthlySummaryResponse(BaseModel):
    """Monthly summary."""

    year: int
    month: int
    total_income: Decimal
    total_expense: Decimal
    balance: Decimal
    income_by_category: list[CategoryTotalResponse]
    expense_by_category: list[CategoryTotalResponse]


class BudgetResponse(BaseModel):
    """A monthly budget for a category."""

    id: int
    category_id: int
    category_name: str
    monthly_limit: Decimal
    spent: Decimal
    remaining: Decimal


class BudgetCreate(BaseModel):
    """Create or update a budget for a category."""

    category_id: int
    monthly_limit: Decimal = Field(gt=0)


class ReceiptOCRItem(BaseModel):
    """An item parsed from a receipt by OCR."""

    name: str
    qty: Decimal
    unit_price: Decimal | None
    subtotal: Decimal


class ReceiptOCRResponse(BaseModel):
    """OCR result from a receipt image."""

    is_receipt: bool
    merchant: str
    occurred_at: datetime | None
    total_amount: Decimal
    currency: str
    suggested_category: str
    suggested_category_id: int | None
    notes: str
    items: list[ReceiptOCRItem] = Field(default_factory=list)


class LowBalanceStatus(BaseModel):
    """Low-balance alert status for current month."""

    is_low: bool
    balance: Decimal
    threshold: Decimal
    total_income: Decimal
    total_expense: Decimal


class ImportPreviewRow(BaseModel):
    """One row in an import preview."""

    action: str
    row_index: int | None = None
    transaction_id: int | None = None
    type: str
    amount: Decimal
    category_name: str
    note: str | None
    occurred_at: datetime | None


class ImportPreviewResponse(BaseModel):
    """Preview of an import: rows that would be created/updated/deleted plus errors."""

    plan_id: str
    to_create: list[ImportPreviewRow]
    to_update: list[ImportPreviewRow]
    to_delete: list[ImportPreviewRow]
    errors: list[str]


class ImportApplyRequest(BaseModel):
    """Apply a previously-previewed import plan."""

    plan_id: str


class ImportApplyResponse(BaseModel):
    """Result of applying an import plan."""

    created: int
    updated: int
    deleted: int


class LinkCodeResponse(BaseModel):
    """Link-code to bind a Telegram chat to an email account."""

    code: str
    expires_at: datetime


class SubscriptionStatusResponse(BaseModel):
    """Current subscription state for the authenticated user."""

    state: str
    active: bool
    can_write: bool
    expires_at: datetime | None
    days_left: int
    has_pending_payment: bool
    monthly_price: Decimal
    currency: str
    billing_instructions: str


class PaymentSubmitRequest(BaseModel):
    """User-submitted manual payment claim."""

    amount: Decimal = Field(gt=0)
    method: str = Field(min_length=1, max_length=32)
    proof_note: str | None = Field(default=None, max_length=500)


class PaymentResponse(BaseModel):
    """A payment row (user view)."""

    id: int
    amount: Decimal
    method: str
    proof_note: str | None
    status: str
    period_start: datetime | None
    period_end: datetime | None
    decided_at: datetime | None
    rejection_reason: str | None
    created_at: datetime


class AdminPaymentResponse(PaymentResponse):
    """A payment row enriched with the requesting user's email/first_name (admin view)."""

    user_id: int
    user_email: str | None
    user_first_name: str | None


class PaymentRejectRequest(BaseModel):
    """Reason for rejecting a payment."""

    reason: str = Field(min_length=1, max_length=255)
