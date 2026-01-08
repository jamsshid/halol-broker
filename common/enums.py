from enum import Enum


class AccountType(str, Enum):
    """Account types"""

    DEMO = "demo"
    REAL = "real"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class AccountStatus(str, Enum):
    """Account status"""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    PENDING_KYC = "pending_kyc"
    MARGIN_CALL = "margin_call"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class TransactionType(str, Enum):
    """Transaction types"""

    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    TRADE_LOCK = "trade_lock"
    TRADE_RELEASE = "trade_release"
    TRADE_PNL = "trade_pnl"
    FEE = "fee"
    COMMISSION = "commission"
    SWAP = "swap"
    BONUS = "bonus"
    REFUND = "refund"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class TransactionStatus(str, Enum):
    """Transaction status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class PaymentMethod(str, Enum):
    """Payment methods"""

    VISA = "visa"
    MASTERCARD = "mastercard"
    CRYPTO_BTC = "crypto_btc"
    CRYPTO_ETH = "crypto_eth"
    CRYPTO_USDT = "crypto_usdt"
    CRYPTO_USDC = "crypto_usdc"
    BANK_TRANSFER = "bank_transfer"
    ISLAMIC_GATEWAY = "islamic_gateway"
    PAYPAL = "paypal"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]

    @classmethod
    def crypto_methods(cls):
        return [cls.CRYPTO_BTC, cls.CRYPTO_ETH, cls.CRYPTO_USDT, cls.CRYPTO_USDC]

    @classmethod
    def card_methods(cls):
        return [cls.VISA, cls.MASTERCARD]


class ComplianceMode(str, Enum):
    """Compliance modes"""

    STANDARD = "standard"
    SHARIAT_COMPLIANT = "shariat_compliant" 
    ULTRA_CALM = "ULTRA_CALM"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class OrderSide(str, Enum):
    """Order side (buy/sell)"""

    BUY = "buy"
    SELL = "sell"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class OrderType(str, Enum):
    """Order types"""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class OrderStatus(str, Enum):
    """Order status"""

    PENDING = "pending"
    EXECUTED = "executed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class CalmMode(str, Enum):
    """Calm modes"""

    OFF = "off"
    SEMI = "semi"
    ULTRA = "ultra"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]
