class TradingPlatformException(Exception):
    """Base exception for all trading platform errors"""

    def __init__(self, message, code=None, details=None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class InsufficientBalanceError(TradingPlatformException):
    """Raised when account has insufficient balance for operation"""

    def __init__(self, message="Insufficient balance", details=None):
        super().__init__(message=message, code="INSUFFICIENT_BALANCE", details=details)


class AccountSuspendedError(TradingPlatformException):
    """Raised when trying to trade on suspended account"""

    def __init__(self, message="Account is suspended", details=None):
        super().__init__(message=message, code="ACCOUNT_SUSPENDED", details=details)


class DailyLossLimitExceeded(TradingPlatformException):
    """Raised when daily loss limit is exceeded"""

    def __init__(self, message="Daily loss limit exceeded", details=None):
        super().__init__(message=message, code="DAILY_LOSS_EXCEEDED", details=details)


class MaxLeverageExceeded(TradingPlatformException):
    """Raised when requested leverage exceeds account maximum"""

    def __init__(self, message="Maximum leverage exceeded", details=None):
        super().__init__(message=message, code="MAX_LEVERAGE_EXCEEDED", details=details)


class InvalidAccountTypeError(TradingPlatformException):
    """Raised when operation is not allowed for account type"""

    def __init__(self, message="Invalid account type for this operation", details=None):
        super().__init__(message=message, code="INVALID_ACCOUNT_TYPE", details=details)


class KYCNotVerifiedError(TradingPlatformException):
    """Raised when KYC verification is required"""

    def __init__(self, message="KYC verification required", details=None):
        super().__init__(message=message, code="KYC_NOT_VERIFIED", details=details)


class WithdrawalLimitExceeded(TradingPlatformException):
    """Raised when withdrawal limit is exceeded"""

    def __init__(self, message="Withdrawal limit exceeded", details=None):
        super().__init__(
            message=message, code="WITHDRAWAL_LIMIT_EXCEEDED", details=details
        )


class PaymentGatewayError(TradingPlatformException):
    """Raised when payment gateway operation fails"""

    def __init__(self, message="Payment gateway error", details=None):
        super().__init__(message=message, code="PAYMENT_GATEWAY_ERROR", details=details)


class ShariahComplianceError(TradingPlatformException):
    """Raised when operation violates Shariah compliance rules"""

    def __init__(self, message="Operation violates Shariah compliance", details=None):
        super().__init__(message=message, code="SHARIAH_VIOLATION", details=details)


class MaxPositionSizeExceeded(TradingPlatformException):
    """Raised when position size exceeds account limit"""

    def __init__(self, message="Maximum position size exceeded", details=None):
        super().__init__(
            message=message, code="MAX_POSITION_SIZE_EXCEEDED", details=details
        )


class MarginCallError(TradingPlatformException):
    """Raised when margin level is too low"""

    def __init__(self, message="Margin call - insufficient margin", details=None):
        super().__init__(message=message, code="MARGIN_CALL", details=details)


class SecurityException(TradingPlatformException):
    """
    Raised when a security or isolation rule is violated.

    Example: trying to apply DEMO trade PnL to a REAL account.
    """

    def __init__(self, message="Security violation", details=None):
        super().__init__(message=message, code="SECURITY_VIOLATION", details=details)


<<<<<<< HEAD
class RiskLimitExceeded(TradingPlatformException):
    """Raised when risk limit is exceeded (daily loss, leverage, etc.)"""

    def __init__(self, message="Risk limit exceeded", details=None):
        super().__init__(message=message, code="RISK_LIMIT_EXCEEDED", details=details)
=======
class TradeValidationError(TradingPlatformException):
    """Raised when trade validation fails (SL not set, invalid price, etc.)"""

    def __init__(self, message="Trade validation failed", details=None):
        super().__init__(message=message, code="TRADE_VALIDATION_ERROR", details=details)


class MarketDataError(TradingPlatformException):
    """Raised when market data is unavailable or invalid"""

    def __init__(self, message="Market data error", details=None):
        super().__init__(message=message, code="MARKET_DATA_ERROR", details=details)


class RiskLimitError(TradingPlatformException):
    """Raised when risk limits are exceeded"""

    def __init__(self, message="Risk limit exceeded", details=None):
        super().__init__(message=message, code="RISK_LIMIT_ERROR", details=details)
>>>>>>> 1500818 (bek1)
