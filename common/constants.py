from decimal import Decimal


class RiskLimits:
    """Default risk limits"""

    # Leverage limits per instrument type
    MAX_LEVERAGE = {
        "default": 100,
        "crypto": 50,
        "forex": 500,
        "commodities": 200,
        "indices": 300,
        "stocks": 20,
    }

    # Loss limits
    MAX_DAILY_LOSS_PERCENT = Decimal("5.0")  # 5% of balance
    MAX_WEEKLY_LOSS_PERCENT = Decimal("10.0")  # 10% of balance
    MAX_MONTHLY_LOSS_PERCENT = Decimal("20.0")  # 20% of balance

    # Position limits
    MAX_POSITION_PERCENT = Decimal("20.0")  # 20% per position
    MAX_OPEN_POSITIONS = 10
    MAX_LOT_SIZE = Decimal("100.0")

    # Margin limits
    MARGIN_CALL_LEVEL = Decimal("120.0")  # 120%
    STOP_OUT_LEVEL = Decimal("80.0")  # 80%

    # Shariat compliance limits
    MAX_OVERNIGHT_POSITION_SHARIAT = Decimal("50.0")  # % of balance
    FORBIDDEN_INSTRUMENTS_SHARIAT = [
        "interest_futures",
        "alcohol",
        "gambling",
        "pork",
        "tobacco",
        "weapons",
        "adult_entertainment",
    ]


class HalalCrypto:
    """Halal cryptocurrency list"""
    
    HALAL_COINS = [
        "BTC",   # Bitcoin
        "ETH",   # Ethereum
        "USDT",  # Tether
        "USDC",  # USD Coin
        "BNB",   # Binance Coin
        "XRP",   # Ripple
        "ADA",   # Cardano
        "SOL",   # Solana
        "DOT",   # Polkadot
        "MATIC", # Polygon
        "LINK",  # Chainlink
        "UNI",   # Uniswap
        "AVAX",  # Avalanche
        "ATOM",  # Cosmos
        "ALGO",  # Algorand
    ]
    
    @classmethod
    def is_halal(cls, symbol: str) -> bool:
        """Check if crypto symbol is halal"""
        # Remove common prefixes/suffixes
        symbol_clean = symbol.upper().replace("BTC", "").replace("ETH", "").replace("USDT", "").replace("USDC", "")
        if symbol_clean:
            symbol_clean = symbol.split("/")[0] if "/" in symbol else symbol
        
        return symbol_clean.upper() in cls.HALAL_COINS or any(
            coin in symbol.upper() for coin in cls.HALAL_COINS
        )

    # Account balance limits
    MIN_BALANCE_DEMO = Decimal("10000.00")
    MIN_BALANCE_REAL = Decimal("100.00")
    MAX_BALANCE_DEMO = Decimal("1000000.00")


class Fees:
    """Fee structures"""

    # Spread markup
    SPREAD_MARKUP = Decimal("0.0001")  # 0.01%

    # Commission per lot
    COMMISSION_PER_LOT = Decimal("5.00")

    # Withdrawal fees
    WITHDRAW_FEE_PERCENT = Decimal("0.5")  # 0.5%
    WITHDRAW_FEE_MIN = Decimal("5.00")
    WITHDRAW_FEE_MAX = Decimal("50.00")

    # Crypto withdrawal fees (fixed)
    CRYPTO_WITHDRAW_FEES = {
        "crypto_btc": Decimal("0.0005"),  # 0.0005 BTC
        "crypto_eth": Decimal("0.005"),  # 0.005 ETH
        "crypto_usdt": Decimal("10.00"),  # 10 USDT
        "crypto_usdc": Decimal("10.00"),  # 10 USDC
    }

    # Swap rates (overnight holding fee)
    SWAP_RATE_LONG = Decimal("0.0001")  # 0.01% per day
    SWAP_RATE_SHORT = Decimal("0.0002")  # 0.02% per day

    # Inactivity fee
    INACTIVITY_FEE_MONTHS = 6
    INACTIVITY_FEE_AMOUNT = Decimal("10.00")  # per month


class Limits:
    """Transaction and operational limits"""

    # Deposit limits
    MIN_DEPOSIT = Decimal("10.00")
    MAX_DEPOSIT_UNVERIFIED = Decimal("1000.00")
    MAX_DEPOSIT_VERIFIED = Decimal("50000.00")
    MAX_DAILY_DEPOSITS = Decimal("100000.00")

    # Withdrawal limits
    MIN_WITHDRAWAL = Decimal("10.00")
    MAX_WITHDRAWAL_UNVERIFIED = Decimal("500.00")
    MAX_WITHDRAWAL_VERIFIED = Decimal("50000.00")
    MAX_DAILY_WITHDRAWALS = Decimal("100000.00")

    # Daily transaction counts
    MAX_DEPOSITS_PER_DAY = 10
    MAX_WITHDRAWALS_PER_DAY = 5
    MAX_TRADES_PER_DAY = 500


class Timeouts:
    """Timeout values in seconds"""

    ORDER_EXECUTION_TIMEOUT = 30
    PAYMENT_GATEWAY_TIMEOUT = 60
    WEBSOCKET_PING_INTERVAL = 30
    SESSION_TIMEOUT = 3600  # 1 hour
    API_RATE_LIMIT_WINDOW = 60  # 1 minute


class APIRateLimits:
    """API rate limits"""

    # Requests per minute
    AUTHENTICATED_USER = 60
    UNAUTHENTICATED = 10
    ADMIN = 1000

    # Specific endpoints
    TRADING_ENDPOINTS = 30  # per minute
    WALLET_ENDPOINTS = 20  # per minute
    DEPOSIT_WITHDRAWAL = 5  # per minute


class ErrorCodes:
    """Standard error codes"""

    # Authentication errors (1000-1099)
    INVALID_CREDENTIALS = 1000
    TOKEN_EXPIRED = 1001
    INVALID_TOKEN = 1002
    ACCOUNT_LOCKED = 1003

    # Authorization errors (1100-1199)
    INSUFFICIENT_PERMISSIONS = 1100
    KYC_REQUIRED = 1101

    # Validation errors (1200-1299)
    INVALID_INPUT = 1200
    MISSING_REQUIRED_FIELD = 1201
    INVALID_FORMAT = 1202

    # Balance errors (1300-1399)
    INSUFFICIENT_BALANCE = 1300
    INSUFFICIENT_MARGIN = 1301
    DAILY_LOSS_EXCEEDED = 1302

    # Trading errors (1400-1499)
    INVALID_SYMBOL = 1400
    MARKET_CLOSED = 1401
    MAX_LEVERAGE_EXCEEDED = 1402
    MAX_POSITION_SIZE_EXCEEDED = 1403

    # Payment errors (1500-1599)
    PAYMENT_FAILED = 1500
    WITHDRAWAL_PENDING = 1501
    PAYMENT_GATEWAY_ERROR = 1502

    # System errors (1600-1699)
    INTERNAL_ERROR = 1600
    SERVICE_UNAVAILABLE = 1601
    RATE_LIMIT_EXCEEDED = 1602


class TradingConstants:
    """Trading engine constants"""
    
    # Position size calculation
    MIN_POSITION_SIZE = Decimal("0.0001")  # Minimum position size
    MAX_POSITION_SIZE = Decimal("1000.0")   # Maximum position size
    
    # Price precision
    PRICE_DECIMAL_PLACES = 6  # For entry_price, stop_loss, take_profit
    PNL_DECIMAL_PLACES = 2    # For PnL calculations
    SIZE_DECIMAL_PLACES = 4   # For position_size
    
    # Risk validation thresholds
    MIN_RISK_PERCENT = Decimal("0.01")  # 0.01% minimum risk
    MAX_RISK_PERCENT = Decimal("10.0")  # 10% maximum risk per trade
    
    # Balance checks
    MIN_BALANCE_FOR_TRADE = Decimal("10.00")  # Minimum balance to open trade
    
    # Partial close thresholds
    PARTIAL_CLOSE_MIN_SIZE = Decimal("0.0001")  # Minimum size for partial close
    FULL_CLOSE_THRESHOLD = Decimal("0.0001")     # Below this = full close
    
    # PnL calculation
    PNL_QUANTIZE_STEP = Decimal("0.01")  # Round PnL to 2 decimal places
    
    # Market data
    PRICE_FETCH_TIMEOUT = 5  # seconds
    PRICE_STALE_THRESHOLD = 60  # seconds - price older than this is stale
    
    # Trade validation
    SL_MANDATORY = True  # Stop Loss is mandatory
    TP_OPTIONAL = True   # Take Profit is optional
    
    # Hedge-free logic
    HEDGE_DISABLED_DEFAULT = True  # Default: hedging disabled
