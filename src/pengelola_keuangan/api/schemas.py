"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

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


class UpdateUserRequest(BaseModel):
    """Update profile fields."""

    first_name: str | None = Field(default=None, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


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


class TransactionCreate(BaseModel):
    """Create a new transaction."""

    type: str = Field(pattern="^(in|out)$")
    amount: Decimal = Field(gt=0)
    category_id: int | None = None
    note: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None


class TransactionUpdate(BaseModel):
    """Update fields of an existing transaction."""

    amount: Decimal | None = Field(default=None, gt=0)
    category_id: int | None = None
    note: str | None = Field(default=None, max_length=255)
    occurred_at: datetime | None = None


class TransactionResponse(BaseModel):
    """A transaction row."""

    id: int
    type: str
    amount: Decimal
    category_id: int | None
    category_name: str | None
    note: str | None
    occurred_at: datetime


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


class LinkCodeResponse(BaseModel):
    """Link-code to bind a Telegram chat to an email account."""

    code: str
    expires_at: datetime
