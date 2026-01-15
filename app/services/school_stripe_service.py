import stripe
import logging
from datetime import datetime
from app.config import get_settings
from app.db.supabase import get_supabase_client
from app.services.email_service import EmailService
from typing import Optional

logger = logging.getLogger(__name__)

settings = get_settings()

# Set Stripe API key - will be None if not configured
if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key
else:
    logger.warning("STRIPE_SECRET_KEY not configured - payment features will not work")

# School pricing: 7500 RMB (approximately $1000 USD)
SCHOOL_PRICES = {
    'CNY': 750000,   # ¥7,500.00
    'USD': 100000,   # $1,000.00
    'EUR': 92000,    # €920.00
    'GBP': 79000,    # £790.00
}


class SchoolStripeService:
    """Service for school Stripe payment operations"""

    PRODUCT_NAME = "EduConnect School Access"
    PRODUCT_DESCRIPTION = "Full access to teacher profiles, CVs, and contact information"

    @staticmethod
    def create_checkout_session(
        school_account_id: int,
        school_email: str,
        success_url: str,
        cancel_url: str,
        currency: str = "CNY"
    ) -> dict:
        """
        Create Stripe Checkout session for school payment (7500 RMB)
        Returns session ID and URL
        """
        # Check Stripe is configured
        if not settings.stripe_secret_key:
            raise ValueError("Payment system not configured. Please contact support.")

        if not school_account_id:
            raise ValueError("school_account_id is required")
        if not school_email:
            raise ValueError("school_email is required")

        supabase = get_supabase_client()

        # Check if school already paid
        school_check = supabase.table("school_accounts").select(
            "has_paid, payment_id, stripe_customer_id"
        ).eq("id", school_account_id).single().execute()

        if school_check.data and school_check.data.get("has_paid"):
            raise ValueError(
                f"School {school_account_id} has already completed payment. "
                f"Payment ID: {school_check.data.get('payment_id')}"
            )

        # Normalize currency
        currency = currency.upper()
        if currency not in SCHOOL_PRICES:
            currency = "CNY"  # Default to CNY for schools

        price_amount = SCHOOL_PRICES[currency]

        # Get or create Stripe customer
        customer_id = school_check.data.get("stripe_customer_id") if school_check.data else None

        if customer_id:
            # Verify customer still exists in Stripe
            try:
                stripe.Customer.retrieve(customer_id)
            except stripe.error.InvalidRequestError:
                customer_id = None

        if not customer_id:
            customer = stripe.Customer.create(
                email=school_email,
                metadata={
                    "school_account_id": school_account_id,
                    "type": "school"
                }
            )
            customer_id = customer.id

            # Save customer ID to school account
            supabase.table("school_accounts").update({
                "stripe_customer_id": customer_id
            }).eq("id", school_account_id).execute()

        # Create checkout session
        # Don't specify payment_method_types to let Stripe auto-select based on
        # what's enabled in dashboard and supported for the currency
        try:
            session_params = {
                "customer": customer_id,
                "line_items": [
                    {
                        "price_data": {
                            "currency": currency.lower(),
                            "product_data": {
                                "name": SchoolStripeService.PRODUCT_NAME,
                                "description": SchoolStripeService.PRODUCT_DESCRIPTION,
                            },
                            "unit_amount": price_amount,
                        },
                        "quantity": 1,
                    }
                ],
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "school_account_id": str(school_account_id),
                    "school_email": school_email,
                    "currency": currency,
                    "type": "school",
                    "created_at": datetime.now().isoformat(),
                },
            }

            # Only add payment_method_types if using USD (card only)
            # For other currencies, let Stripe auto-detect available methods
            if currency == "USD":
                session_params["payment_method_types"] = ["card"]

            session = stripe.checkout.Session.create(**session_params)

            return {
                "session_id": session.id,
                "url": session.url,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e.user_message if hasattr(e, 'user_message') else str(e)}")
            raise ValueError(f"Payment system error: {e.user_message if hasattr(e, 'user_message') else 'Unable to create checkout session'}")

    @staticmethod
    def handle_school_checkout_completed(session: dict):
        """
        Handle successful school checkout session
        Update school payment status, create payment record, and send confirmation email
        """
        supabase = get_supabase_client()

        session_metadata = session.get("metadata", {})

        # Only process school payments
        if session_metadata.get("type") != "school":
            return

        school_account_id_str = session_metadata.get("school_account_id")
        if not school_account_id_str:
            raise ValueError("Session metadata missing school_account_id")

        school_account_id = int(school_account_id_str)
        payment_intent_id = session["payment_intent"]
        customer_id = session["customer"]
        amount_total = session["amount_total"]

        # Retrieve payment details
        receipt_url = None
        payment_method = None
        try:
            payment_intent = stripe.PaymentIntent.retrieve(
                payment_intent_id,
                expand=['charges']
            )
            payment_method = payment_intent.get("payment_method")

            if hasattr(payment_intent, 'charges') and payment_intent.charges and payment_intent.charges.data:
                receipt_url = payment_intent.charges.data[0].receipt_url
        except stripe.error.InvalidRequestError:
            pass

        # Check idempotency - don't process same payment twice
        existing = supabase.table("school_payments").select("id").eq(
            "stripe_payment_intent_id", payment_intent_id
        ).execute()

        if existing.data:
            return

        # Create payment record
        payment_data = {
            "school_account_id": school_account_id,
            "stripe_payment_intent_id": payment_intent_id,
            "stripe_customer_id": customer_id,
            "amount": amount_total,
            "currency": session["currency"].upper(),
            "status": "succeeded",
            "payment_method": payment_method,
            "receipt_url": receipt_url,
        }

        supabase.table("school_payments").insert(payment_data).execute()

        # Update school account payment status
        supabase.table("school_accounts").update({
            "has_paid": True,
            "payment_id": payment_intent_id,
            "payment_date": "now()",
        }).eq("id", school_account_id).execute()

        # Send confirmation email
        school = supabase.table("school_accounts").select(
            "contact_email, school_name"
        ).eq("id", school_account_id).single().execute()

        if school.data:
            try:
                EmailService.send_school_payment_confirmation(
                    to_email=school.data["contact_email"],
                    school_name=school.data["school_name"],
                    amount=amount_total,
                    currency=session["currency"].upper()
                )
                logger.info(f"School payment confirmation sent: {school.data['school_name']}")
            except Exception as e:
                logger.error(f"Failed to send school payment confirmation: {e}")

    @staticmethod
    def get_payment_by_school(school_account_id: int) -> Optional[dict]:
        """Get payment record for a school"""
        supabase = get_supabase_client()

        response = supabase.table("school_payments").select("*").eq(
            "school_account_id", school_account_id
        ).order("created_at", desc=True).limit(1).execute()

        return response.data[0] if response.data else None

    @staticmethod
    def verify_and_process_session(session_id: str, school_account_id: int) -> dict:
        """
        Verify a Stripe Checkout session and process payment if needed.
        Fallback mechanism for when webhooks fail.
        """
        if not session_id or not session_id.startswith('cs_'):
            raise ValueError("Invalid session ID format")

        supabase = get_supabase_client()

        # Check if school already has payment recorded
        school_record = supabase.table("school_accounts").select(
            "has_paid, payment_id"
        ).eq("id", school_account_id).single().execute()

        if school_record.data and school_record.data.get("has_paid"):
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

        # Validate session belongs to this school
        session_school_id = session.get("metadata", {}).get("school_account_id")
        if session_school_id and int(session_school_id) != school_account_id:
            raise ValueError("Session does not belong to this school")

        # Check payment status
        if session.payment_status != "paid":
            return {
                "already_processed": False,
                "verified": False,
                "has_paid": False,
                "message": f"Payment not completed. Status: {session.payment_status}"
            }

        # Payment succeeded - process it
        session_dict = {
            "id": session.id,
            "payment_intent": session.payment_intent,
            "customer": session.customer,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "payment_status": session.payment_status,
            "metadata": dict(session.metadata) if session.metadata else {}
        }

        SchoolStripeService.handle_school_checkout_completed(session_dict)

        return {
            "already_processed": False,
            "verified": True,
            "has_paid": True,
            "message": "Payment verified and processed successfully"
        }
