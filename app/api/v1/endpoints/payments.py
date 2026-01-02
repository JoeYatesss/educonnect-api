from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.models.payment import CheckoutSessionCreate, CheckoutSessionResponse, PaymentResponse
from app.dependencies import get_current_teacher
from app.services.stripe_service import StripeService
from app.middleware.rate_limit import limiter


router = APIRouter()


@router.post("/create-checkout-session", response_model=CheckoutSessionResponse)
@limiter.limit("3/hour")
async def create_checkout_session(
    request: Request,
    session_data: CheckoutSessionCreate,
    teacher: dict = Depends(get_current_teacher)
):
    """
    Create Stripe Checkout session for teacher payment
    Rate limited to 3 requests per hour per user
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
            cancel_url=session_data.cancel_url
        )

        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {str(e)}"
        )


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
