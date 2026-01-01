from trading.models import Position
from trading.services.validation import validate_halal_trade
from trading.services.risk import calculate_position_size


def open_trade(
    *,
    account,
    instrument,
    side,
    mode,
    entry_price,
    stop_loss,
    take_profit,
    risk_percent
):
    # 1. Halol & risk validation
    validate_halal_trade(account, instrument, risk_percent)

    # 2. Position size (% risk)
    position_size = calculate_position_size(
        balance=account.balance,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss=stop_loss
    )

    # 3. Create position
    position = Position.objects.create(
        account=account,
        instrument=instrument,
        side=side,
        mode=mode,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_percent=risk_percent,
        position_size=position_size,
    )

    return position
