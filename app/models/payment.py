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
    currency: Optional[str] = None  # GBP, EUR, or USD


class CheckoutSessionResponse(BaseModel):
    session_id: str
    url: str


class CurrencyDetectionResponse(BaseModel):
    detected_country: str
    detected_country_name: str
    detected_currency: str
    preferred_currency: Optional[str]
    effective_currency: str
    price_amount: int
    price_formatted: str
    available_currencies: list[str]


class SetCurrencyRequest(BaseModel):
    currency: str = Field(..., min_length=3, max_length=3, description="Currency code: GBP, EUR, or USD")


class VerifySessionRequest(BaseModel):
    session_id: str = Field(..., description="Stripe Checkout Session ID (cs_...)")
