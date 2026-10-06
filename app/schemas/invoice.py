from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceItemInput(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class InvoiceInput(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=50)
    customer_id: int = Field(gt=0)
    invoice_date: date
    due_date: date
    tax: Decimal = Field(default=0, ge=0, le=100, max_digits=5, decimal_places=2, description="Tax rate as a percentage")
    status: str = Field(default="draft", pattern="^(draft|sent|paid|overdue|cancelled)$")
    notes: str | None = Field(default=None, max_length=500)
    items: list[InvoiceItemInput] = Field(min_length=1)


class PaymentInput(BaseModel):
    invoice_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payment_date: date
    payment_method: str = Field(pattern="^(cash|bank_transfer|upi|card|other)$")
    reference: str | None = Field(default=None, max_length=100)


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    invoice_number: str
    customer_id: int
    invoice_date: date
    due_date: date
    subtotal: Decimal
    tax: Decimal
    total_amount: Decimal
    status: str
    notes: str | None
    items: list[InvoiceItemInput]
