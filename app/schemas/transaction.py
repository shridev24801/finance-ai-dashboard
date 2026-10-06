from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionInput(BaseModel):
    type: str = Field(pattern="^(income|expense)$")
    category: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: Optional[str] = Field(default=None, max_length=500)
    transaction_date: date
    reference: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default="completed", pattern="^(pending|completed|cancelled)$")


class TransactionResponse(TransactionInput):
    model_config = ConfigDict(from_attributes=True)
    id: int

