from fastapi import APIRouter, Request, HTTPException, status
from app.services.stripe_service import StripeService
import stripe


router = APIRouter()


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events
    Verifies webhook signature and processes events
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header"
        )

    try:
        event = StripeService.construct_webhook_event(payload, sig_header)
    except ValueError:
        # Invalid payload
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        try:
            StripeService.handle_checkout_completed(session)
        except Exception as e:
            # Return 500 so Stripe retries the webhook
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process webhook"
            )
    elif event["type"] == "payment_intent.payment_failed":
        # Log failed payment - handled internally
        pass

    return {"status": "success"}
