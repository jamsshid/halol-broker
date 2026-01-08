from decimal import Decimal, ROUND_HALF_UP
import uuid
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional
from constants import Fees


def generate_account_number(account_type: str) -> str:
    """Generate unique account number"""
    import random

    prefix = "D" if account_type == "demo" else "R"
    number = random.randint(10000000, 99999999)
    return f"{prefix}{number}"


def generate_transaction_id() -> str:
    """Generate unique transaction ID"""
    return f"TXN{uuid.uuid4().hex[:12].upper()}"


def round_decimal(value: Decimal, decimal_places: int = 2) -> Decimal:
    """Round decimal to specified places"""
    quantize_value = Decimal("0.1") ** decimal_places
    return value.quantize(quantize_value, rounding=ROUND_HALF_UP)


def calculate_percentage(part: Decimal, whole: Decimal) -> Decimal:
    """Calculate percentage"""
    if whole == 0:
        return Decimal("0.00")
    return (part / whole) * 100


def format_currency(amount: Decimal, currency: str = "USD") -> str:
    """Format currency for display"""
    symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
    }
    symbol = symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"


def validate_crypto_address(address: str, crypto_type: str) -> bool:
    """Validate cryptocurrency address format"""
    validators = {
        "crypto_btc": lambda a: len(a) >= 26 and len(a) <= 35,
        "crypto_eth": lambda a: len(a) == 42 and a.startswith("0x"),
        "crypto_usdt": lambda a: len(a) == 42 and a.startswith("0x"),
    }
    validator = validators.get(crypto_type)
    return validator(address) if validator else False


def calculate_margin_requirement(
    volume: Decimal, price: Decimal, leverage: int
) -> Decimal:
    """Calculate margin requirement for position"""
    position_value = volume * price
    return round_decimal(position_value / leverage)


def calculate_pip_value(
    symbol: str, lot_size: Decimal, account_currency: str = "USD"
) -> Decimal:
    """Calculate pip value for forex pair"""
    # Simplified calculation
    # In production, this should consider actual pair specifications
    return lot_size * Decimal("10.0")


def is_market_open(symbol: str) -> bool:
    """Check if market is open for trading"""
    # Simplified - in production, check actual market hours
    now = datetime.now()

    # Crypto markets are always open
    if symbol.startswith("BTC") or symbol.startswith("ETH"):
        return True

    # Forex market (Sunday 5pm - Friday 5pm EST)
    weekday = now.weekday()
    if weekday == 6:  # Sunday
        return now.hour >= 17
    elif weekday == 5:  # Saturday
        return False
    else:
        return True


def calculate_swap(
    position_value: Decimal, side: str, is_shariat: bool = False
) -> Decimal:
    """Calculate overnight swap fee"""
    if is_shariat:
        return Decimal("0.00")  # No swap for Islamic accounts

    rate = Fees.SWAP_RATE_LONG if side == "buy" else Fees.SWAP_RATE_SHORT
    return round_decimal(position_value * rate)


def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate HMAC signature for webhook"""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    expected = generate_webhook_signature(payload, secret)
    return hmac.compare_digest(expected, signature)


class DateTimeUtils:
    """DateTime utility functions"""

    @staticmethod
    def get_trading_day_start() -> datetime:
        """Get start of current trading day"""
        now = datetime.now()
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def get_week_start() -> datetime:
        """Get start of current week"""
        now = datetime.now()
        days_since_monday = now.weekday()
        return now - timedelta(days=days_since_monday)

    @staticmethod
    def get_month_start() -> datetime:
        """Get start of current month"""
        now = datetime.now()
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
