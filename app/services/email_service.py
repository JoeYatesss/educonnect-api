import resend
from app.config import get_settings
from typing import Optional
from datetime import datetime


class EmailService:
    """Service for sending emails via Resend"""

    def __init__(self):
        settings = get_settings()
        resend.api_key = settings.resend_api_key

    @staticmethod
    def format_currency(amount: int, currency: str) -> str:
        """Format amount based on currency (amount in minor units)"""
        amount_major = amount / 100
        currency_symbols = {
            'USD': '$',
            'GBP': '£',
            'EUR': '€',
        }
        symbol = currency_symbols.get(currency.upper(), currency.upper() + ' ')
        return f"{symbol}{amount_major:.2f}"

    @staticmethod
    def send_payment_confirmation(
        to_email: str,
        teacher_name: str,
        amount: int,  # in minor units (cents/pence)
        currency: str,
        payment_date: str,
        receipt_url: Optional[str] = None
    ) -> dict:
        """
        Send payment confirmation and welcome package email

        Args:
            to_email: Teacher's email address
            teacher_name: Teacher's full name
            amount: Payment amount in minor units (e.g., 9900 for $99.00, 1000 for £10.00)
            currency: Currency code (USD, GBP, EUR, etc.)
            payment_date: ISO format datetime string
            receipt_url: Optional Stripe receipt URL

        Returns:
            dict: Response from Resend API
        """
        # Initialize settings
        settings = get_settings()
        resend.api_key = settings.resend_api_key

        # Format amount as currency
        formatted_amount = EmailService.format_currency(amount, currency)

        # Format date
        try:
            formatted_date = datetime.fromisoformat(payment_date.replace('Z', '+00:00')).strftime('%B %d, %Y')
        except:
            formatted_date = datetime.now().strftime('%B %d, %Y')

        # Build HTML email
        html_content = EmailService._build_welcome_email_html(
            teacher_name=teacher_name,
            amount=formatted_amount,
            payment_date=formatted_date,
            receipt_url=receipt_url
        )

        # Send email
        params = {
            "from": "EduConnect <noreply@jjtechnologies.co.uk>",
            "to": [to_email],
            "subject": f"Welcome to EduConnect! Payment Confirmed - {formatted_amount}",
            "html": html_content,
        }

        return resend.Emails.send(params)

    @staticmethod
    def _build_welcome_email_html(
        teacher_name: str,
        amount: str,
        payment_date: str,
        receipt_url: Optional[str]
    ) -> str:
        """Build HTML email template for payment confirmation"""

        receipt_section = ""
        if receipt_url:
            receipt_section = f"""
            <p style="margin: 0 0 10px 0;">
                <a href="{receipt_url}"
                   style="color: #EF4444; text-decoration: none; font-weight: 500;">
                    Download Receipt →
                </a>
            </p>
            """

        # Professional HTML email template
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #F9FAFB;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff;">

                <!-- Header -->
                <div style="background: linear-gradient(135deg, #EF4444 0%, #F97316 100%); padding: 40px 30px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700;">
                        Welcome to EduConnect!
                    </h1>
                    <p style="color: rgba(255, 255, 255, 0.9); margin: 10px 0 0 0; font-size: 16px;">
                        Your teaching journey in China starts now
                    </p>
                </div>

                <!-- Payment Confirmation Section -->
                <div style="padding: 40px 30px; border-bottom: 1px solid #E5E7EB;">
                    <div style="background-color: #F0FDF4; border-left: 4px solid #10B981; padding: 20px; margin-bottom: 30px;">
                        <h2 style="color: #065F46; margin: 0 0 10px 0; font-size: 18px; font-weight: 600;">
                            ✓ Payment Confirmed
                        </h2>
                        <p style="color: #047857; margin: 0; font-size: 14px;">
                            Your payment has been successfully processed.
                        </p>
                    </div>

                    <div style="background-color: #F9FAFB; padding: 20px; border-radius: 8px;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 10px 0; color: #6B7280; font-size: 14px;">Amount Paid:</td>
                                <td style="padding: 10px 0; color: #111827; font-size: 14px; font-weight: 600; text-align: right;">
                                    {amount}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; color: #6B7280; font-size: 14px;">Payment Date:</td>
                                <td style="padding: 10px 0; color: #111827; font-size: 14px; text-align: right;">
                                    {payment_date}
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; color: #6B7280; font-size: 14px;">Payment Type:</td>
                                <td style="padding: 10px 0; color: #111827; font-size: 14px; text-align: right;">
                                    One-time payment
                                </td>
                            </tr>
                        </table>
                    </div>

                    <div style="margin-top: 20px;">
                        {receipt_section}
                    </div>
                </div>

                <!-- Next Steps Section -->
                <div style="padding: 40px 30px; border-bottom: 1px solid #E5E7EB;">
                    <h2 style="color: #111827; margin: 0 0 20px 0; font-size: 22px; font-weight: 600;">
                        What's Next?
                    </h2>

                    <div style="margin-bottom: 20px;">
                        <div style="margin-bottom: 20px;">
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 36px; vertical-align: top; padding-right: 15px;">
                                        <div style="background-color: #EF4444; color: white; width: 28px; height: 28px; border-radius: 50%; text-align: center; line-height: 28px; font-weight: 600; font-size: 14px;">
                                            1
                                        </div>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <h3 style="color: #111827; margin: 0 0 5px 0; font-size: 16px; font-weight: 600;">
                                            Complete Your Profile
                                        </h3>
                                        <p style="color: #6B7280; margin: 0; font-size: 14px; line-height: 1.5;">
                                            Add your teaching experience, qualifications, and preferences to help us match you with the perfect schools.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>

                        <div style="margin-bottom: 20px;">
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 36px; vertical-align: top; padding-right: 15px;">
                                        <div style="background-color: #EF4444; color: white; width: 28px; height: 28px; border-radius: 50%; text-align: center; line-height: 28px; font-weight: 600; font-size: 14px;">
                                            2
                                        </div>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <h3 style="color: #111827; margin: 0 0 5px 0; font-size: 16px; font-weight: 600;">
                                            Browse Matched Schools
                                        </h3>
                                        <p style="color: #6B7280; margin: 0; font-size: 14px; line-height: 1.5;">
                                            View schools that match your profile, including salary ranges, locations, and benefits packages.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>

                        <div style="margin-bottom: 20px;">
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 36px; vertical-align: top; padding-right: 15px;">
                                        <div style="background-color: #EF4444; color: white; width: 28px; height: 28px; border-radius: 50%; text-align: center; line-height: 28px; font-weight: 600; font-size: 14px;">
                                            3
                                        </div>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <h3 style="color: #111827; margin: 0 0 5px 0; font-size: 16px; font-weight: 600;">
                                            Submit Applications
                                        </h3>
                                        <p style="color: #6B7280; margin: 0; font-size: 14px; line-height: 1.5;">
                                            Apply to schools directly through our platform. We'll handle the coordination with school administrators.
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </div>

                    <div style="text-align: center; margin-top: 30px;">
                        <a href="https://educonnectchina.com/dashboard"
                           style="display: inline-block; background-color: #EF4444; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
                            Go to Dashboard →
                        </a>
                    </div>
                </div>

                <!-- Platform Features Section -->
                <div style="padding: 40px 30px; background-color: #F9FAFB;">
                    <h2 style="color: #111827; margin: 0 0 20px 0; font-size: 22px; font-weight: 600;">
                        Your Platform Benefits
                    </h2>

                    <div style="margin-bottom: 15px;">
                        <div style="margin-bottom: 12px;">
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 30px; vertical-align: top; padding-right: 10px;">
                                        <span style="color: #10B981; font-size: 20px;">✓</span>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <p style="color: #374151; margin: 0; font-size: 14px;">
                                            <strong>Smart Matching Algorithm:</strong> AI-powered matching based on your qualifications and preferences
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>

                        <div style="margin-bottom: 12px;">
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 30px; vertical-align: top; padding-right: 10px;">
                                        <span style="color: #10B981; font-size: 20px;">✓</span>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <p style="color: #374151; margin: 0; font-size: 14px;">
                                            <strong>Full School Details:</strong> Access salary ranges, benefits, and location information
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>

                        <div style="margin-bottom: 12px;">
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 30px; vertical-align: top; padding-right: 10px;">
                                        <span style="color: #10B981; font-size: 20px;">✓</span>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <p style="color: #374151; margin: 0; font-size: 14px;">
                                            <strong>Unlimited Applications:</strong> Apply to as many schools as you want
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>

                        <div style="margin-bottom: 12px;">
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 30px; vertical-align: top; padding-right: 10px;">
                                        <span style="color: #10B981; font-size: 20px;">✓</span>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <p style="color: #374151; margin: 0; font-size: 14px;">
                                            <strong>Direct Communication:</strong> Connect directly with school administrators
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>

                        <div style="margin-bottom: 12px;">
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 30px; vertical-align: top; padding-right: 10px;">
                                        <span style="color: #10B981; font-size: 20px;">✓</span>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <p style="color: #374151; margin: 0; font-size: 14px;">
                                            <strong>100+ Partner Schools:</strong> Your profile is visible to our network of verified schools
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>

                        <div>
                            <table style="width: 100%;">
                                <tr>
                                    <td style="width: 30px; vertical-align: top; padding-right: 10px;">
                                        <span style="color: #10B981; font-size: 20px;">✓</span>
                                    </td>
                                    <td style="vertical-align: top;">
                                        <p style="color: #374151; margin: 0; font-size: 14px;">
                                            <strong>Dedicated Support:</strong> Our placement team is here to help you every step of the way
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Money-Back Guarantee -->
                <div style="padding: 30px; background-color: #DBEAFE; border-top: 3px solid #3B82F6; text-align: center;">
                    <p style="color: #1E40AF; margin: 0; font-size: 14px; font-weight: 600;">
                        🛡️ 90-Day Money-Back Guarantee
                    </p>
                    <p style="color: #1E3A8A; margin: 5px 0 0 0; font-size: 13px;">
                        If we don't find you a suitable match within 90 days, we'll refund your payment.
                    </p>
                </div>

                <!-- Footer -->
                <div style="padding: 30px; text-align: center; background-color: #111827;">
                    <p style="color: #9CA3AF; margin: 0 0 10px 0; font-size: 14px;">
                        Need help? Contact us at
                        <a href="mailto:team@educonnectchina.com" style="color: #EF4444; text-decoration: none;">
                            team@educonnectchina.com
                        </a>
                    </p>
                    <p style="color: #6B7280; margin: 0; font-size: 12px;">
                        © 2026 EduConnect. All rights reserved.
                    </p>
                </div>

            </div>
        </body>
        </html>
        """
