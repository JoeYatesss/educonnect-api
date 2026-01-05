from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.models.payment import (
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    PaymentResponse,
    CurrencyDetectionResponse,
    SetCurrencyRequest,
    VerifySessionRequest
)
from app.dependencies import get_current_teacher
from app.services.stripe_service import StripeService
from app.services.location_service import LocationService
from app.db.supabase import get_supabase_client
from app.middleware.rate_limit import limiter


router = APIRouter()


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
@limiter.limit("20/hour")
async def create_checkout_session(
    request: Request,
    session_data: CheckoutSessionCreate,
    teacher: dict = Depends(get_current_teacher)
):
    """
    Create Stripe Checkout session for teacher payment
    Rate limited to 20 requests per hour per user
    """
    # Check if teacher already paid
    if teacher.get("has_paid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment already completed"
        )

    try:
        session = StripeService.create_checkout_session(
            teacher_id=teacher["id"],
            teacher_email=teacher["email"],
            success_url=session_data.success_url,
            cancel_url=session_data.cancel_url,
            currency=session_data.currency
        )

        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )


@router.get("/detect-currency", response_model=CurrencyDetectionResponse)
async def detect_currency(
    request: Request,
    teacher: dict = Depends(get_current_teacher)
):
    """
    Detect user's currency based on IP location
    """
    # Get client IP
    client_ip = request.client.host
    if forwarded := request.headers.get("x-forwarded-for"):
        client_ip = forwarded.split(",")[0].strip()

    print(f"[PaymentsAPI] Detecting currency for IP: {client_ip}")

    # Detect country/currency
    detection = LocationService.detect_country_from_ip(client_ip)

    # Save to database if not already set
    supabase = get_supabase_client()
    if not teacher.get("detected_country"):
        print(f"[PaymentsAPI] Saving detected country/currency for teacher {teacher['id']}")
        supabase.table("teachers").update({
            "detected_country": detection["country_code"],
            "detected_currency": detection["currency"]
        }).eq("id", teacher["id"]).execute()

    # Determine effective currency
    effective_currency = (
        teacher.get("preferred_currency") or
        detection["currency"]
    )

    return CurrencyDetectionResponse(
        detected_country=detection["country_code"],
        detected_country_name=detection["country_name"],
        detected_currency=detection["currency"],
        preferred_currency=teacher.get("preferred_currency"),
        effective_currency=effective_currency,
        price_amount=LocationService.get_price_amount(effective_currency),
        price_formatted=LocationService.format_price(
            LocationService.get_price_amount(effective_currency),
            effective_currency
        ),
        available_currencies=LocationService.get_all_currencies()
    )


@router.post("/set-currency")
async def set_currency(
    currency_request: SetCurrencyRequest,
    teacher: dict = Depends(get_current_teacher)
):
    """
    Save user's manually selected currency preference
    """
    if currency_request.currency.upper() not in ["GBP", "EUR", "USD"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid currency. Must be GBP, EUR, or USD"
        )

    currency = currency_request.currency.upper()
    print(f"[PaymentsAPI] Setting currency preference for teacher {teacher['id']}: {currency}")

    supabase = get_supabase_client()
    supabase.table("teachers").update({
        "preferred_currency": currency
    }).eq("id", teacher["id"]).execute()

    return {
        "success": True,
        "currency": currency,
        "price_formatted": LocationService.format_price(
            LocationService.get_price_amount(currency),
            currency
        )
    }


@router.get("/me", response_model=PaymentResponse, status_code=status.HTTP_200_OK)
async def get_my_payment(teacher: dict = Depends(get_current_teacher)):
    """
    Get payment record for current teacher
    """
    payment = StripeService.get_payment_by_teacher(teacher["id"])

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No payment found"
        )

    return payment


@router.post("/verify-session")
async def verify_payment_session(
    request_data: VerifySessionRequest,
    teacher: dict = Depends(get_current_teacher)
):
    """
    Verify a Stripe Checkout session and update DB if payment succeeded.

    This is a fallback mechanism for when webhooks fail or are unreachable
    (e.g., local development). It's idempotent - safe to call multiple times.

    Returns:
        - already_processed: true if payment was already recorded
        - verified: true if payment was verified and DB updated
        - has_paid: current payment status
    """
    try:
        result = StripeService.verify_and_process_session(
            session_id=request_data.session_id,
            teacher_id=teacher["id"]
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify session: {str(e)}"
        )
