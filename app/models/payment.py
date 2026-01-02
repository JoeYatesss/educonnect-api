from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentCreate(BaseModel):
    teacher_id: int
    amount: int = Field(..., description="Amount in cents")
    currency: str = Field(default="USD", max_length=3)


class PaymentResponse(BaseModel):
    id: int
    teacher_id: int
    stripe_payment_intent_id: str
    stripe_customer_id: Optional[str]
    amount: int
    currency: str
    status: PaymentStatus
    payment_method: Optional[str]
    receipt_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CheckoutSessionCreate(BaseModel):
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    session_id: str
    url: str
