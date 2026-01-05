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

    # Enhanced request logging
    from datetime import datetime
    print(f"\n{'='*80}")
    print(f"[Webhook] REQUEST RECEIVED at {datetime.now().isoformat()}")
    print(f"[Webhook] Payload size: {len(payload)} bytes")
    print(f"[Webhook] Has stripe-signature header: {bool(sig_header)}")
    print(f"{'='*80}\n")

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
    print(f"\n{'='*60}")
    print(f"[Webhook] Received event: {event['type']}")
    print(f"[Webhook] Event ID: {event.get('id')}")
    print(f"{'='*60}\n")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"\n{'='*80}")
        print(f"[Webhook] Processing checkout.session.completed")
        print(f"[Webhook] Session ID: {session.get('id')}")
        print(f"[Webhook] Payment Status: {session.get('payment_status')}")
        print(f"[Webhook] Customer ID: {session.get('customer')}")
        print(f"[Webhook] Payment Intent: {session.get('payment_intent')}")
        print(f"[Webhook] Amount: ${session.get('amount_total', 0) / 100:.2f}")
        print(f"[Webhook] Currency: {session.get('currency', 'unknown').upper()}")

        # Enhanced metadata logging
        import json
        metadata = session.get('metadata', {})
        print(f"\n[Webhook] METADATA DETAILS:")
        print(json.dumps(metadata, indent=2))
        print(f"[Webhook] Teacher ID from metadata: {metadata.get('teacher_id')}")
        print(f"[Webhook] Teacher Email from metadata: {metadata.get('teacher_email')}")
        print(f"{'='*80}\n")

        try:
            StripeService.handle_checkout_completed(session)
            print(f"[Webhook] ✅ Successfully processed checkout completion")
        except Exception as e:
            print(f"\n{'='*80}")
            print(f"[Webhook] ❌ ERROR processing checkout: {str(e)}")
            print(f"[Webhook] Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            print(f"{'='*80}\n")

            # Return 500 so Stripe retries the webhook
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process webhook: {str(e)}"
            )
    elif event["type"] == "payment_intent.succeeded":
        # Already handled in checkout.session.completed
        print(f"[Webhook] payment_intent.succeeded - already handled in checkout.session.completed")
    elif event["type"] == "payment_intent.payment_failed":
        # Log failed payment
        payment_intent = event["data"]["object"]
        print(f"[Webhook] Payment failed: {payment_intent['id']}")
    else:
        print(f"[Webhook] Unhandled event type: {event['type']}")

    return {"status": "success"}


@router.post("/stripe/test")
async def test_stripe_webhook():
    """
    Test endpoint to verify webhook processing works
    Only for development - remove in production

    This endpoint allows testing the webhook handler logic without
    needing to trigger actual Stripe events via CLI.

    Usage:
        curl -X POST http://localhost:8000/api/v1/webhooks/stripe/test
    """
    print("\n" + "="*80)
    print("[TEST] Manual webhook test triggered")
    print("="*80 + "\n")

    # Create a mock session object matching Stripe's checkout.session.completed structure
    mock_session = {
        "id": "cs_test_manual_123456",
        "object": "checkout.session",
        "payment_intent": "pi_test_manual_123456",
        "customer": "cus_test_manual_123456",
        "amount_total": 1499,  # $14.99 in cents
        "currency": "usd",
        "payment_status": "paid",
        "metadata": {
            "teacher_id": "999",  # Use a test teacher ID or change this
            "teacher_email": "test@example.com"
        }
    }

    print("[TEST] Mock session created:")
    import json
    print(json.dumps(mock_session, indent=2))

    try:
        StripeService.handle_checkout_completed(mock_session)
        return {
            "status": "success",
            "message": "Test webhook processed successfully",
            "session_id": mock_session["id"]
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[TEST] ❌ Error: {str(e)}")
        print(error_trace)
        return {
            "status": "error",
            "message": str(e),
            "error_type": type(e).__name__,
            "traceback": error_trace
        }
