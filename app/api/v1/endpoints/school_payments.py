from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from app.dependencies import get_current_school_account
from app.services.school_stripe_service import SchoolStripeService, SCHOOL_PRICES
from app.services.email_service import EmailService
from app.db.supabase import get_supabase_client
from app.middleware.rate_limit import limiter
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class SchoolCheckoutSessionCreate(BaseModel):
    """Request to create a checkout session"""
    success_url: str
    cancel_url: str
    currency: Optional[str] = "CNY"


class SchoolCheckoutSessionResponse(BaseModel):
    """Response with checkout session details"""
    session_id: str
    checkout_url: str


class VerifySessionRequest(BaseModel):
    """Request to verify a checkout session"""
    session_id: str


class ManualPaymentRequest(BaseModel):
    """Request for manual/invoice payment"""
    company_name: str
    billing_address: str
    additional_notes: Optional[str] = None


@router.post("/create-checkout-session", response_model=SchoolCheckoutSessionResponse)
@limiter.limit("20/hour")
async def create_school_checkout_session(
    request: Request,
    session_data: SchoolCheckoutSessionCreate,
    school: dict = Depends(get_current_school_account)
):
    """Create Stripe Checkout session for school payment (7500 RMB)"""
    if school.get("has_paid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already completed"
        )

    try:
        session = SchoolStripeService.create_checkout_session(
            school_account_id=school["id"],
            school_email=school["contact_email"],
            success_url=session_data.success_url,
            cancel_url=session_data.cancel_url,
            currency=session_data.currency or "CNY"
        )
        return {"session_id": session["session_id"], "checkout_url": session["url"]}
    except ValueError as e:
        logger.error(f"ValueError creating checkout session: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create checkout session: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )


@router.get("/detect-currency")
async def detect_currency(
    request: Request,
    school: dict = Depends(get_current_school_account)
):
    """Detect currency for school (defaults to CNY)"""
    from app.services.location_service import LocationService

    # Get client IP
    client_ip = request.client.host
    if forwarded := request.headers.get("x-forwarded-for"):
        client_ip = forwarded.split(",")[0].strip()

    # Detect country from IP
    detection = LocationService.detect_country_from_ip(client_ip)

    # For schools, default to CNY unless they've set a preference
    effective_currency = school.get("preferred_currency") or "CNY"

    # Get price for effective currency
    price_amount = SCHOOL_PRICES.get(effective_currency, SCHOOL_PRICES["CNY"])

    # Format price for display
    currency_formats = {
        "CNY": f"¥{price_amount / 100:,.0f}",
        "USD": f"${price_amount / 100:,.0f}",
        "EUR": f"€{price_amount / 100:,.0f}",
        "GBP": f"£{price_amount / 100:,.0f}",
    }
    price_formatted = currency_formats.get(effective_currency, f"{effective_currency} {price_amount / 100:,.0f}")

    return {
        "detected_country": detection.get("country_code"),
        "detected_currency": detection.get("currency"),
        "effective_currency": effective_currency,
        "price_amount": price_amount,
        "price_formatted": price_formatted,
        "available_currencies": list(SCHOOL_PRICES.keys())
    }


@router.post("/set-currency")
@limiter.limit("30/hour")
async def set_currency(
    request: Request,
    currency: str,
    school: dict = Depends(get_current_school_account)
):
    """Set preferred currency for school"""
    currency = currency.upper()

    if currency not in SCHOOL_PRICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid currency. Available: {list(SCHOOL_PRICES.keys())}"
        )

    supabase = get_supabase_client()

    supabase.table("school_accounts").update({
        "preferred_currency": currency
    }).eq("id", school["id"]).execute()

    return {"message": "Currency preference saved", "currency": currency}


@router.get("/me")
async def get_school_payment(
    school: dict = Depends(get_current_school_account)
):
    """Get payment record for current school"""
    payment = SchoolStripeService.get_payment_by_school(school["id"])

    if not payment:
        return {"has_payment": False, "payment": None}

    return {"has_payment": True, "payment": payment}


@router.post("/verify-session")
@limiter.limit("30/hour")
async def verify_session(
    request: Request,
    data: VerifySessionRequest,
    school: dict = Depends(get_current_school_account)
):
    """
    Verify and process a checkout session.
    Fallback for when webhooks fail or are unreachable.
    """
    try:
        result = SchoolStripeService.verify_and_process_session(
            session_id=data.session_id,
            school_account_id=school["id"]
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to verify session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify session"
        )


@router.post("/manual-payment-request")
@limiter.limit("5/day")
async def request_manual_payment(
    request: Request,
    data: ManualPaymentRequest,
    school: dict = Depends(get_current_school_account)
):
    """Request manual/invoice payment option"""
    if school.get("has_paid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already completed"
        )

    supabase = get_supabase_client()

    # Check if there's already a pending request
    existing = supabase.table("school_invoice_requests").select("id, status").eq(
        "school_account_id", school["id"]
    ).eq("status", "pending").execute()

    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pending invoice request. Please wait for it to be processed."
        )

    try:
        # Save invoice request to database
        invoice_data = {
            "school_account_id": school["id"],
            "company_name": data.company_name,
            "billing_address": data.billing_address,
            "additional_notes": data.additional_notes,
            "amount": SCHOOL_PRICES.get("CNY", 750000),
            "currency": "CNY",
            "status": "pending"
        }

        result = supabase.table("school_invoice_requests").insert(invoice_data).execute()

        # Send notification email to admin
        EmailService.send_manual_payment_request(
            school_name=school["school_name"],
            contact_email=school["contact_email"],
            contact_name=school.get("contact_name"),
            city=school.get("city"),
            company_name=data.company_name,
            billing_address=data.billing_address,
            additional_notes=data.additional_notes
        )

        logger.info(f"Manual payment request saved and notification sent for: {school['school_name']}")
        return {
            "message": "Invoice request submitted. Our team will review and send you an invoice within 1-2 business days.",
            "submitted": True,
            "request_id": result.data[0]["id"] if result.data else None
        }
    except Exception as e:
        logger.error(f"Failed to process manual payment request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit request. Please try again or contact us directly."
        )


@router.get("/invoice-requests")
async def get_invoice_requests(
    school: dict = Depends(get_current_school_account)
):
    """Get invoice requests for current school"""
    supabase = get_supabase_client()

    result = supabase.table("school_invoice_requests").select("*").eq(
        "school_account_id", school["id"]
    ).order("created_at", desc=True).execute()

    return {"requests": result.data or []}
