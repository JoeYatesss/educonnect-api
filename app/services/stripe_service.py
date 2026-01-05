import stripe
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

        print(f"[StripeService] Creating checkout session for teacher_id={teacher_id}, email={teacher_email}")

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
        print(f"[StripeService] Using currency: {currency}, price_id: {price_id}")

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
                print(f"[Stripe] Customer {customer_id} not found, creating new customer")
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
        print(f"[StripeService] Creating Stripe checkout session...")
        print(f"[StripeService] Metadata will include: teacher_id={teacher_id}, teacher_email={teacher_email}")

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

        # Validate metadata was set correctly
        created_metadata = session.get("metadata", {})
        if not created_metadata.get("teacher_id"):
            raise ValueError(f"CRITICAL: Stripe session created without teacher_id in metadata! Session ID: {session.id}")

        print(f"[StripeService] ✅ Checkout session created successfully")
        print(f"[StripeService] Session ID: {session.id}")
        print(f"[StripeService] Metadata: {created_metadata}")
        print(f"[StripeService] URL: {session.url}")

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
        print(f"[StripeService] Starting handle_checkout_completed")
        supabase = get_supabase_client()

        # Enhanced metadata validation with fallback
        import json
        session_metadata = session.get("metadata", {})
        print(f"[StripeService] Full session metadata: {json.dumps(session_metadata, indent=2)}")

        if not session_metadata:
            raise ValueError("Session has no metadata object")

        teacher_id_str = session_metadata.get("teacher_id")
        teacher_id = None

        if not teacher_id_str:
            # Fallback: try to find teacher by email
            teacher_email = session_metadata.get("teacher_email")
            if teacher_email:
                print(f"[StripeService] No teacher_id, trying email lookup: {teacher_email}")
                teacher_result = supabase.table("teachers").select("id").eq(
                    "email", teacher_email
                ).single().execute()
                if teacher_result.data:
                    teacher_id = teacher_result.data["id"]
                    print(f"[StripeService] Found teacher via email: {teacher_id}")
                else:
                    raise ValueError(f"No teacher found with email: {teacher_email}")
            else:
                raise ValueError("Session metadata missing both teacher_id and teacher_email")
        else:
            teacher_id = int(teacher_id_str)

        payment_intent_id = session["payment_intent"]
        customer_id = session["customer"]
        amount_total = session["amount_total"]

        print(f"[StripeService] Processing payment for teacher_id: {teacher_id}")
        print(f"[StripeService] Payment intent: {payment_intent_id}")
        print(f"[StripeService] Amount: {amount_total}")

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
                print(f"[StripeService] Receipt URL: {receipt_url}")
        except stripe.error.InvalidRequestError as e:
            # This is likely a test event from 'stripe trigger' with a fake payment intent
            print(f"[StripeService] ⚠️  Could not retrieve payment intent (likely a test event): {str(e)}")
            print(f"[StripeService] Continuing without receipt URL...")

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
            print(f"[StripeService] Payment already exists, skipping duplicate processing")
            return

        # Insert payment record
        print(f"[StripeService] Creating payment record in database")
        payment_record = supabase.table("payments").insert(payment_data).execute()
        print(f"[StripeService] Payment record created: {payment_record.data}")

        # Update teacher payment status
        print(f"[StripeService] Updating teacher has_paid status to True for teacher_id: {teacher_id}")
        update_result = supabase.table("teachers").update({
            "has_paid": True,
            "payment_id": payment_intent_id,
            "payment_date": "now()",
        }).eq("id", teacher_id).execute()
        print(f"[StripeService] Teacher update result: {update_result.data}")

        if update_result.data:
            print(f"[StripeService] ✓ Successfully updated has_paid=True for teacher {teacher_id}")
        else:
            print(f"[StripeService] ✗ WARNING: Teacher update returned no data!")

        # Email sending disabled for test mode (no domain configured)
        # Uncomment when domain is set up and Resend is configured

        # # Get teacher details for email
        # teacher = supabase.table("teachers").select(
        #     "email, first_name, last_name"
        # ).eq("id", teacher_id).single().execute()

        # if teacher.data:
        #     teacher_email = teacher.data.get("email")
        #     first_name = teacher.data.get("first_name", "")
        #     last_name = teacher.data.get("last_name", "")
        #     teacher_name = f"{first_name} {last_name}".strip() or "Valued Teacher"

        #     # Send payment confirmation email
        #     try:
        #         email_service = EmailService()
        #         email_service.send_payment_confirmation(
        #             to_email=teacher_email,
        #             teacher_name=teacher_name,
        #             amount=amount_total,  # Amount in cents
        #             payment_date=payment_record.data[0]["created_at"],
        #             receipt_url=receipt_url
        #         )
        #         print(f"[Email] Payment confirmation sent to {teacher_email}")
        #     except Exception as email_error:
        #         # Log error but don't fail the webhook
        #         # Payment is already processed, email is secondary
        #         print(f"[Email Error] Failed to send confirmation email: {email_error}")

        print(f"[StripeService] ℹ️  Email sending disabled (test mode, no domain configured)")

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
        print(f"[StripeService] Verifying session {session_id} for teacher {teacher_id}")

        # Validate session_id format
        if not session_id or not session_id.startswith('cs_'):
            raise ValueError("Invalid session ID format")

        supabase = get_supabase_client()

        # Check if teacher already has payment recorded
        teacher_record = supabase.table("teachers").select(
            "has_paid, payment_id"
        ).eq("id", teacher_id).single().execute()

        if teacher_record.data and teacher_record.data.get("has_paid"):
            print(f"[StripeService] Teacher {teacher_id} already marked as paid")
            return {
                "already_processed": True,
                "verified": True,
                "has_paid": True,
                "message": "Payment already recorded"
            }

        # Retrieve session from Stripe
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.InvalidRequestError as e:
            print(f"[StripeService] Invalid session ID: {e}")
            raise ValueError(f"Invalid or expired session: {session_id}")

        # Validate session belongs to this teacher
        session_teacher_id = session.get("metadata", {}).get("teacher_id")
        if session_teacher_id and int(session_teacher_id) != teacher_id:
            print(f"[StripeService] Session teacher_id mismatch: {session_teacher_id} != {teacher_id}")
            raise ValueError("Session does not belong to this teacher")

        # Check payment status
        if session.payment_status != "paid":
            print(f"[StripeService] Session not paid: {session.payment_status}")
            return {
                "already_processed": False,
                "verified": False,
                "has_paid": False,
                "message": f"Payment not completed. Status: {session.payment_status}"
            }

        # Payment succeeded - process it using existing handler
        # This is idempotent (checks for existing payment record)
        print(f"[StripeService] Processing verified session via fallback")

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
