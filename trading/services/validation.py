from decimal import Decimal
from common.constants import HalalCrypto


def validate_halal_trade(account, instrument, risk_percent):
    """
    Validate halal trade requirements.
    
    Args:
        account: TradeAccount instance
        instrument: Instrument instance
        risk_percent: Risk percentage
    """
    # 1. Instrument halal check
    if not instrument.is_halal:
        raise ValueError("Instrument is not halal")

    # 2. Crypto halal filter
    if instrument.is_crypto:
        if not HalalCrypto.is_halal(instrument.symbol):
            raise ValueError(f"Crypto {instrument.symbol} is not in halal list")
    
    # 3. Risk per trade limit
    if risk_percent <= 0:
        raise ValueError("Risk must be positive")

    if risk_percent > account.max_risk_per_trade:
        raise ValueError(
            f"Max risk per trade is {account.max_risk_per_trade}%"
        )

    # 4. Demo / Real basic check
    if account.balance <= Decimal("0"):
        raise ValueError("Insufficient balance")
