from decimal import Decimal
from common.constants import RiskLimits


def calculate_position_size(balance, risk_percent, entry_price, stop_loss):
    """
    Lot-free position size calculation.
    Risk = balance * %
    Position size = risk / SL distance
    """
    risk_amount = balance * Decimal(risk_percent / 100)
    stop_distance = abs(entry_price - stop_loss)

    if stop_distance <= 0:
        raise ValueError("Invalid stop loss distance")

    position_size = risk_amount / stop_distance
    return position_size.quantize(Decimal("0.0001"))


def validate_leverage(account, instrument):
    """
    Validate leverage against max limits (1:500 for forex).
    """
    # Get max leverage for instrument type
    instrument_type = "crypto" if instrument.is_crypto else "forex"
    max_leverage = RiskLimits.MAX_LEVERAGE.get(instrument_type, RiskLimits.MAX_LEVERAGE["default"])
    
    # Check account leverage
    account_leverage = getattr(account, 'max_leverage', None) or max_leverage
    
    if account_leverage > max_leverage:
        raise ValueError(
            f"Leverage {account_leverage}:1 exceeds maximum {max_leverage}:1 for {instrument_type}"
        )
    
    # Forex max is 1:500
    if instrument_type == "forex" and account_leverage > 500:
        raise ValueError("Forex leverage cannot exceed 1:500")
    
    return True
