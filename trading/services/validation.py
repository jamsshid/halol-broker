from decimal import Decimal


def validate_halal_trade(account, instrument, risk_percent):
    # 1. Instrument halalmi?
    if not instrument.is_halal:
        raise ValueError("Instrument is not halal")

    # 2. Risk per trade limit
    if risk_percent <= 0:
        raise ValueError("Risk must be positive")

    if risk_percent > account.max_risk_per_trade:
        raise ValueError(
            f"Max risk per trade is {account.max_risk_per_trade}%"
        )

    # 3. Demo / Real basic check
    if account.balance <= Decimal("0"):
        raise ValueError("Insufficient balance")
