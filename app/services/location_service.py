import httpx
from typing import Dict, Optional
from app.config import get_settings

# Price amounts in minor units (cents/pence)
PRICE_AMOUNTS = {
    'GBP': 1000,   # £10.00
    'EUR': 1199,   # €11.99
    'USD': 1499,   # $14.99
}

# Currency symbols
CURRENCY_SYMBOLS = {
    'GBP': '£',
    'EUR': '€',
    'USD': '$',
}

# Country code to currency mapping
# GBP: United Kingdom + territories
GBP_COUNTRIES = {'GB', 'IM', 'JE', 'GG'}

# EUR: Eurozone countries (19 core + 6 territories/agreements)
EUR_COUNTRIES = {
    # Core Eurozone
    'AT', 'BE', 'CY', 'EE', 'FI', 'FR', 'DE', 'GR', 'IE', 'IT',
    'LV', 'LT', 'LU', 'MT', 'NL', 'PT', 'SK', 'SI', 'ES',
    # Territories and agreements
    'AD', 'MC', 'SM', 'VA', 'ME', 'XK'
}

# USD: United States + territories (default for all others)
USD_COUNTRIES = {'US', 'PR', 'VI', 'GU', 'AS', 'MP'}


class LocationService:
    """Service for detecting user location and determining currency"""

    @staticmethod
    def detect_country_from_ip(ip_address: str) -> Dict[str, str]:
        """
        Detect country from IP address using ip-api.com

        Args:
            ip_address: IP address to lookup

        Returns:
            dict with country_code, country_name, and currency
        """
        # Handle localhost and private IPs
        if ip_address in ['127.0.0.1', 'localhost', '::1'] or ip_address.startswith('192.168.') or ip_address.startswith('10.'):
            return {
                'country_code': 'US',
                'country_name': 'United States',
                'currency': 'USD'
            }

        try:
            # Call ip-api.com (free, 45 req/min, no API key required)
            with httpx.Client(timeout=3.0) as client:
                response = client.get(
                    f'http://ip-api.com/json/{ip_address}',
                    params={'fields': 'status,country,countryCode'}
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get('status') == 'success':
                        country_code = data.get('countryCode', 'US')
                        country_name = data.get('country', 'United States')
                        currency = LocationService.get_currency_for_country(country_code)

                        return {
                            'country_code': country_code,
                            'country_name': country_name,
                            'currency': currency
                        }

        except Exception as e:
            print(f"[LocationService] Error detecting country from IP {ip_address}: {e}")

        # Default to USD if detection fails
        return {
            'country_code': 'US',
            'country_name': 'United States',
            'currency': 'USD'
        }

    @staticmethod
    def get_currency_for_country(country_code: str) -> str:
        """
        Map country code to currency

        Args:
            country_code: ISO 3166-1 alpha-2 country code

        Returns:
            Currency code (GBP, EUR, or USD)
        """
        country_code = country_code.upper()

        if country_code in GBP_COUNTRIES:
            return 'GBP'
        elif country_code in EUR_COUNTRIES:
            return 'EUR'
        else:
            # Default to USD for all other countries
            return 'USD'

    @staticmethod
    def get_price_id_for_currency(currency: str) -> str:
        """
        Get Stripe Price ID for currency from environment settings.

        Args:
            currency: Currency code (GBP, EUR, USD)

        Returns:
            Stripe Price ID

        Raises:
            ValueError: If price ID is not configured for the currency
        """
        settings = get_settings()
        currency = currency.upper()

        price_ids = {
            'GBP': settings.stripe_price_id_gbp,
            'EUR': settings.stripe_price_id_eur,
            'USD': settings.stripe_price_id_usd,
        }

        price_id = price_ids.get(currency) or price_ids.get('USD')

        if not price_id:
            raise ValueError(
                f"Stripe price ID not configured for currency '{currency}'. "
                f"Set STRIPE_PRICE_ID_{currency} environment variable."
            )

        return price_id

    @staticmethod
    def get_price_amount(currency: str) -> int:
        """
        Get price amount in minor units for currency

        Args:
            currency: Currency code (GBP, EUR, USD)

        Returns:
            Price in minor units (cents/pence)
        """
        currency = currency.upper()
        return PRICE_AMOUNTS.get(currency, PRICE_AMOUNTS['USD'])

    @staticmethod
    def format_price(amount: int, currency: str) -> str:
        """
        Format price with currency symbol

        Args:
            amount: Amount in minor units (cents/pence)
            currency: Currency code (GBP, EUR, USD)

        Returns:
            Formatted price string (e.g., "£10.00", "€11.99", "$14.99")
        """
        currency = currency.upper()
        symbol = CURRENCY_SYMBOLS.get(currency, currency + ' ')
        amount_major = amount / 100
        return f"{symbol}{amount_major:.2f}"

    @staticmethod
    def get_all_currencies() -> list:
        """Get list of all supported currencies"""
        return ['GBP', 'EUR', 'USD']
