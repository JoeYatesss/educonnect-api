import stripe
from app.config import get_settings
from app.db.supabase import get_supabase_client
from typing import Optional


settings = get_settings()
stripe.api_key = settings.stripe_secret_key


class StripeService:
    """Service for Stripe payment operations"""

    PRODUCT_NAME = "EduConnect Platform Access"
    PRODUCT_DESCRIPTION = "One-time fee to access school matching and application services"
    AMOUNT = 9900  # $99.00 in cents

    @staticmethod
    def create_checkout_session(
        teacher_id: int,
        teacher_email: str,
        success_url: str,
        cancel_url: str
    ) -> dict:
        """
        Create Stripe Checkout session for one-time payment
        Returns session ID and URL
        """
        supabase = get_supabase_client()

        # Check if teacher already has a Stripe customer ID
        teacher = supabase.table("teachers").select("stripe_customer_id").eq("id", teacher_id).single().execute()

        customer_id = teacher.data.get("stripe_customer_id") if teacher.data else None

        # Create or retrieve Stripe customer
        if not customer_id:
            customer = stripe.Customer.create(
                email=teacher_email,
                metadata={"teacher_id": teacher_id}
            )
            customer_id = customer.id

            # Save customer ID to teacher record
            supabase.table("teachers").update({
                "stripe_customer_id": customer_id
            }).eq("id", teacher_id).execute()

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": StripeService.PRODUCT_NAME,
                            "description": StripeService.PRODUCT_DESCRIPTION,
                        },
                        "unit_amount": StripeService.AMOUNT,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "teacher_id": teacher_id,
            },
        )

        return {
            "session_id": session.id,
            "url": session.url,
        }

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str):
        """
        Construct and verify webhook event from Stripe
        Raises exception if signature is invalid
        """
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )

    @staticmethod
    def handle_checkout_completed(session: dict):
        """
        Handle successful checkout session
        Update teacher payment status and create payment record
        """
        supabase = get_supabase_client()

        teacher_id = int(session["metadata"]["teacher_id"])
        payment_intent_id = session["payment_intent"]
        customer_id = session["customer"]
        amount_total = session["amount_total"]

        # Retrieve payment intent to get payment details
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        # Create payment record
        payment_data = {
            "teacher_id": teacher_id,
            "stripe_payment_intent_id": payment_intent_id,
            "stripe_customer_id": customer_id,
            "amount": amount_total,
            "currency": session["currency"].upper(),
            "status": "succeeded",
            "payment_method": payment_intent.get("payment_method"),
        }

        # Check if payment already exists (idempotency)
        existing = supabase.table("payments").select("id").eq(
            "stripe_payment_intent_id", payment_intent_id
        ).execute()

        if existing.data:
            # Payment already processed
            return

        # Insert payment record
        supabase.table("payments").insert(payment_data).execute()

        # Update teacher payment status
        supabase.table("teachers").update({
            "has_paid": True,
            "payment_id": payment_intent_id,
            "payment_date": "now()",
        }).eq("id", teacher_id).execute()

    @staticmethod
    def get_payment_by_teacher(teacher_id: int) -> Optional[dict]:
        """Get payment record for a teacher"""
        supabase = get_supabase_client()

        response = supabase.table("payments").select("*").eq(
            "teacher_id", teacher_id
        ).order("created_at", desc=True).limit(1).execute()

        return response.data[0] if response.data else None
