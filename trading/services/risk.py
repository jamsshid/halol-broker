from decimal import Decimal


def calculate_position_size(balance, risk_percent, entry_price, stop_loss):
    """
    Lot yo‘q.
    Risk = balance * %
    Position size = risk / SL distance
    """
    risk_amount = balance * Decimal(risk_percent / 100)
    stop_distance = abs(entry_price - stop_loss)

    if stop_distance <= 0:
        raise ValueError("Invalid stop loss distance")

    position_size = risk_amount / stop_distance
    return position_size.quantize(Decimal("0.0001"))
