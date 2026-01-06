import stripe
from datetime import datetime
from app.config import get_settings
from app.db.supabase import get_supabase_client
from app.services.email_service import EmailService
from app.services.location_service import LocationService
from typing import Optional


settings = get_settings()
stripe.api_key = settings.stripe_secret_key


class StripeService:
    """Service for Stripe payment operations"""

    PRODUCT_NAME = "EduConnect Platform Access"
    PRODUCT_DESCRIPTION = "One-time fee to access school matching and application services"

    @staticmethod
    def create_checkout_session(
        teacher_id: int,
        teacher_email: str,
        success_url: str,
        cancel_url: str,
        currency: Optional[str] = None
    ) -> dict:
        """
        Create Stripe Checkout session for one-time payment
        Returns session ID and URL
        """
        # Validate inputs
        if not teacher_id:
            raise ValueError("teacher_id is required and cannot be None or 0")
        if not teacher_email:
            raise ValueError("teacher_email is required")

        # Validate teacher exists

        supabase = get_supabase_client()

        # Check if teacher already paid (API-level validation)
        teacher_check = supabase.table("teachers").select(
            "has_paid, payment_id"
        ).eq("id", teacher_id).single().execute()

        if teacher_check.data and teacher_check.data.get("has_paid"):
            raise ValueError(
                f"Teacher {teacher_id} has already completed payment. "
                f"Payment ID: {teacher_check.data.get('payment_id')}"
            )

        # Determine currency priority:
        # 1. User's manual selection (parameter)
        # 2. User's saved preference
        # 3. User's detected currency
        # 4. Default to USD
        if not currency:
            teacher = supabase.table("teachers").select(
                "preferred_currency, detected_currency"
            ).eq("id", teacher_id).single().execute()

            currency = (
                teacher.data.get("preferred_currency") or
                teacher.data.get("detected_currency") or
                "USD"
            )

        # Get Price ID from LocationService
        price_id = LocationService.get_price_id_for_currency(currency)

        # Check if teacher already has a Stripe customer ID
        teacher = supabase.table("teachers").select("stripe_customer_id").eq("id", teacher_id).single().execute()

        customer_id = teacher.data.get("stripe_customer_id") if teacher.data else None

        # Create or retrieve Stripe customer
        if customer_id:
            # Verify customer still exists in Stripe
            try:
                stripe.Customer.retrieve(customer_id)
            except stripe.error.InvalidRequestError:
                # Customer doesn't exist, clear the old ID and create new one
                customer_id = None

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
        from datetime import datetime

        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "teacher_id": str(teacher_id),  # Primary identifier
                    "teacher_email": teacher_email,  # Backup identifier for fallback
                    "currency": currency,  # For tracking
                    "created_at": datetime.now().isoformat(),  # Timestamp for debugging
                },
            )
        except stripe.error.InvalidRequestError as e:
            # Provide helpful error for price ID misconfiguration
            if "No such price" in str(e):
                raise ValueError(
                    f"Stripe price ID '{price_id}' not found. "
                    f"This usually means the price exists in test mode but not live mode, "
                    f"or vice versa. Check STRIPE_PRICE_ID_{currency} environment variable "
                    f"matches your Stripe mode (test/live)."
                ) from e
            raise

        # Validate metadata was set correctly
        created_metadata = session.get("metadata", {})
        if not created_metadata.get("teacher_id"):
            raise ValueError(f"CRITICAL: Stripe session created without teacher_id in metadata! Session ID: {session.id}")

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
        Update teacher payment status, create payment record, and send confirmation email
        """
        supabase = get_supabase_client()

        # Enhanced metadata validation with fallback
        session_metadata = session.get("metadata", {})

        if not session_metadata:
            raise ValueError("Session has no metadata object")

        teacher_id_str = session_metadata.get("teacher_id")
        teacher_id = None

        if not teacher_id_str:
            # Fallback: try to find teacher by email
            teacher_email = session_metadata.get("teacher_email")
            if teacher_email:
                teacher_result = supabase.table("teachers").select("id").eq(
                    "email", teacher_email
                ).single().execute()
                if teacher_result.data:
                    teacher_id = teacher_result.data["id"]
                else:
                    raise ValueError("No teacher found with provided email")
            else:
                raise ValueError("Session metadata missing both teacher_id and teacher_email")
        else:
            teacher_id = int(teacher_id_str)

        payment_intent_id = session["payment_intent"]
        customer_id = session["customer"]
        amount_total = session["amount_total"]

        # Retrieve payment intent to get payment details (expand charges to get receipt)
        # This may fail for test events from 'stripe trigger', so we handle it gracefully
        receipt_url = None
        payment_method = None
        try:
            payment_intent = stripe.PaymentIntent.retrieve(
                payment_intent_id,
                expand=['charges']
            )
            payment_method = payment_intent.get("payment_method")

            # Get receipt URL from charges
            if hasattr(payment_intent, 'charges') and payment_intent.charges and payment_intent.charges.data:
                receipt_url = payment_intent.charges.data[0].receipt_url
        except stripe.error.InvalidRequestError:
            # This is likely a test event from 'stripe trigger' with a fake payment intent
            # Continue without receipt URL
            pass

        # Create payment record
        payment_data = {
            "teacher_id": teacher_id,
            "stripe_payment_intent_id": payment_intent_id,
            "stripe_customer_id": customer_id,
            "amount": amount_total,
            "currency": session["currency"].upper(),
            "status": "succeeded",
            "payment_method": payment_method,  # May be None for test events
            "receipt_url": receipt_url,  # May be None for test events
        }

        # Check if payment already exists (idempotency)
        existing = supabase.table("payments").select("id").eq(
            "stripe_payment_intent_id", payment_intent_id
        ).execute()

        if existing.data:
            # Payment already processed - don't send duplicate email
            return

        # Insert payment record
        supabase.table("payments").insert(payment_data).execute()

        # Update teacher payment status
        supabase.table("teachers").update({
            "has_paid": True,
            "payment_id": payment_intent_id,
            "payment_date": "now()",
        }).eq("id", teacher_id).execute()

        # Send payment confirmation email
        teacher = supabase.table("teachers").select("email, full_name").eq("id", teacher_id).single().execute()
        if teacher.data:
            try:
                EmailService.send_payment_confirmation(
                    to_email=teacher.data["email"],
                    teacher_name=teacher.data.get("full_name", "Teacher"),
                    amount=amount_total,
                    currency=session["currency"].upper(),
                    payment_date=datetime.now().isoformat(),
                    receipt_url=receipt_url
                )
            except Exception as e:
                # Log error but don't fail the payment flow
                print(f"Failed to send confirmation email: {e}")

    @staticmethod
    def get_payment_by_teacher(teacher_id: int) -> Optional[dict]:
        """Get payment record for a teacher"""
        supabase = get_supabase_client()

        response = supabase.table("payments").select("*").eq(
            "teacher_id", teacher_id
        ).order("created_at", desc=True).limit(1).execute()

        return response.data[0] if response.data else None

    @staticmethod
    def verify_and_process_session(session_id: str, teacher_id: int) -> dict:
        """
        Verify a Stripe Checkout session and process payment if needed.

        This is a fallback mechanism for when webhooks fail or are unreachable
        (e.g., local development). It's idempotent - safe to call multiple times.

        Args:
            session_id: The Stripe Checkout Session ID (cs_...)
            teacher_id: The authenticated teacher's ID

        Returns:
            dict with verification status

        Raises:
            ValueError: If session is invalid or doesn't belong to teacher
        """

        # Validate session_id format
        if not session_id or not session_id.startswith('cs_'):
            raise ValueError("Invalid session ID format")

        supabase = get_supabase_client()

        # Check if teacher already has payment recorded
        teacher_record = supabase.table("teachers").select(
            "has_paid, payment_id"
        ).eq("id", teacher_id).single().execute()

        if teacher_record.data and teacher_record.data.get("has_paid"):
            return {
                "already_processed": True,
                "verified": True,
                "has_paid": True,
                "message": "Payment already recorded"
            }

        # Retrieve session from Stripe
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.InvalidRequestError:
            raise ValueError(f"Invalid or expired session: {session_id}")

        # Validate session belongs to this teacher
        session_teacher_id = session.get("metadata", {}).get("teacher_id")
        if session_teacher_id and int(session_teacher_id) != teacher_id:
            raise ValueError("Session does not belong to this teacher")

        # Check payment status
        if session.payment_status != "paid":
            return {
                "already_processed": False,
                "verified": False,
                "has_paid": False,
                "message": f"Payment not completed. Status: {session.payment_status}"
            }

        # Payment succeeded - process it using existing handler
        # This is idempotent (checks for existing payment record)

        # Convert Stripe session object to dict for handle_checkout_completed
        session_dict = {
            "id": session.id,
            "payment_intent": session.payment_intent,
            "customer": session.customer,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "payment_status": session.payment_status,
            "metadata": dict(session.metadata) if session.metadata else {}
        }

        StripeService.handle_checkout_completed(session_dict)

        return {
            "already_processed": False,
            "verified": True,
            "has_paid": True,
            "message": "Payment verified and processed successfully"
        }
