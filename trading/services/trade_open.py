from decimal import Decimal
import logging
from django.utils import timezone
from django.db import transaction
from trading.models import Position
from trading.services.validation import validate_halal_trade
from trading.services.risk import calculate_position_size, validate_leverage
from trading.engine.logging import TradeLogger
from trading.engine.risk_engine import RiskEngine, OrderValidationError
from trading.services.risk_limits import RiskGuard
from common.hooks import notify_trade_opened
from trading.hooks import on_trade_open
from common.exceptions import TradeValidationError, MarketDataError, RiskLimitError
from common.constants import TradingConstants
from calm.helpers import get_mode_policy
from market.price_feed import get_price_feed

logger = logging.getLogger(__name__)


def open_trade(
    *,
    account,
    instrument,
    side,
    mode,
    entry_price,
    stop_loss,
    take_profit=None,  # Optional
    risk_percent,
    timeframe=None
):
    """
    Open a trade position with full error handling and rollback logic.
    
    Args:
        account: TradeAccount instance
        instrument: Instrument instance
        side: 'BUY' or 'SELL'
        mode: 'ULTRA' or 'SEMI'
        entry_price: Entry price (Decimal)
        stop_loss: Stop loss price (MANDATORY)
        take_profit: Take profit price (OPTIONAL)
        risk_percent: Risk percentage
        timeframe: Optional timeframe (M1, M5, H1, D1, etc.)
    
    Returns:
        Position instance
    
    Raises:
        TradeValidationError: If trade validation fails
        MarketDataError: If market data is unavailable
        RiskLimitError: If risk limits are exceeded
    """
    position = None
    error_context = {
        "user_id": account.user.id if account.user else None,
        "account_id": account.id,
        "instrument": instrument.symbol,
        "side": side,
        "mode": mode,
        "entry_price": str(entry_price),
        "stop_loss": str(stop_loss),
    }
    
    try:
        with transaction.atomic():
            # 1. Validate side
            if side not in [Position.Side.BUY, Position.Side.SELL]:
                raise TradeValidationError(
                    f"Invalid side: {side}. Must be BUY or SELL",
                    details=error_context
                )
            
            # 2. Check market data availability
            try:
                price_feed = get_price_feed()
                current_price = price_feed.get_price(instrument.symbol)
                if current_price is None or current_price <= 0:
                    raise MarketDataError(
                        f"Market data unavailable for {instrument.symbol}",
                        details=error_context
                    )
            except Exception as e:
                logger.error(f"Market data error for {instrument.symbol}: {str(e)}", extra=error_context)
                raise MarketDataError(
                    f"Failed to fetch market data for {instrument.symbol}: {str(e)}",
                    details=error_context
                )
            
            # 3. Core order validation (SL mandatory, TP optional, risk, SL distance)
            try:
                RiskEngine.validate_order(
                    account=account,
                    instrument=instrument,
                    side=side,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    risk_percent=risk_percent
                )
            except OrderValidationError as e:
                logger.warning(f"Order validation failed: {str(e)}", extra=error_context)
                raise TradeValidationError(
                    f"Order validation failed: {str(e)}",
                    details={**error_context, "validation_error": str(e)}
                )
            
            # 4. Halol & risk validation
            try:
                validate_halal_trade(account, instrument, risk_percent)
            except ValueError as e:
                logger.warning(f"Halal validation failed: {str(e)}", extra=error_context)
                raise TradeValidationError(
                    f"Halal validation failed: {str(e)}",
                    details={**error_context, "halal_error": str(e)}
                )
            
            # 5. Validate leverage (max 1:500)
            try:
                validate_leverage(account, instrument)
            except ValueError as e:
                logger.warning(f"Leverage validation failed: {str(e)}", extra=error_context)
                raise RiskLimitError(
                    f"Leverage validation failed: {str(e)}",
                    details={**error_context, "leverage_error": str(e)}
                )
            
            # 6. Hedge-free logic check (default disabled)
            hedge_disabled = True  # Default: hedging disabled
            if hedge_disabled:
                # Check for opposite position (hedge prevention)
                opposite_side = Position.Side.SELL if side == Position.Side.BUY else Position.Side.BUY
                existing_opposite = Position.objects.filter(
                    account=account,
                    instrument=instrument,
                    side=opposite_side,
                    status__in=[Position.Status.OPEN, Position.Status.PARTIAL]
                ).exists()
                
                if existing_opposite:
                    raise TradeValidationError(
                        f"Hedging is disabled for this account. "
                        f"Close existing {opposite_side} position for {instrument.symbol} before opening {side} position.",
                        details={**error_context, "hedge_blocked": True}
                    )
            
            # 7. Position size (% risk)
            try:
                position_size = calculate_position_size(
                    balance=account.balance,
                    risk_percent=risk_percent,
                    entry_price=entry_price,
                    stop_loss=stop_loss
                )
            except Exception as e:
                logger.error(f"Position size calculation failed: {str(e)}", extra=error_context)
                raise TradeValidationError(
                    f"Position size calculation failed: {str(e)}",
                    details={**error_context, "position_size_error": str(e)}
                )
            
            # 8. Risk guard (daily loss, per-trade risk) before creating position
            try:
                RiskGuard().enforce(account=account, risk_percent=Decimal(str(risk_percent)), mode=mode)
            except RiskLimitError as e:
                logger.warning(f"Risk guard blocked trade: {str(e)}", extra=error_context)
                raise

            # 9. Mode-based risk policy (not hardcoded)
            try:
                mode_policy = get_mode_policy(mode)
                position_size_percent = (position_size * entry_price / account.balance) * Decimal("100")
                mode_policy.validate_risk(Decimal(str(risk_percent)), position_size_percent)
            except ValueError as e:
                logger.warning(f"Risk limit exceeded: {str(e)}", extra=error_context)
                raise RiskLimitError(
                    f"Risk limit exceeded: {str(e)}",
                    details={**error_context, "risk_limit_error": str(e)}
                )
            
            # 10. Check balance sufficiency (implicit check via position_size)
            required_margin = position_size * entry_price
            if account.balance < TradingConstants.MIN_BALANCE_FOR_TRADE:
                logger.warning(
                    f"Account balance below minimum: {account.balance} < {TradingConstants.MIN_BALANCE_FOR_TRADE}",
                    extra=error_context
                )
                raise RiskLimitError(
                    f"Account balance is too low. Minimum required: {TradingConstants.MIN_BALANCE_FOR_TRADE}",
                    details={**error_context, "min_balance": str(TradingConstants.MIN_BALANCE_FOR_TRADE), "current_balance": str(account.balance)}
                )
            if account.balance < required_margin:
                logger.warning(
                    f"Insufficient balance: required {required_margin}, available {account.balance}",
                    extra=error_context
                )
                raise RiskLimitError(
                    f"Insufficient balance to open this position. Required margin: {required_margin}, Available balance: {account.balance}",
                    details={**error_context, "required_margin": str(required_margin), "available_balance": str(account.balance)}
                )
            
            # 11. Create position (with hedge_disabled flag)
            # If this fails, transaction will rollback automatically
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
                remaining_size=position_size,  # For partial close tracking
                timeframe=timeframe,
                status=Position.Status.OPEN,
                hedge_disabled=hedge_disabled,  # Hedge-free logic (default disabled)
            )
            
            # 11. Log trade open event (outside transaction to avoid rollback)
            # If logging fails, we still want the position created
            try:
                TradeLogger.log_open(position, entry_price)
            except Exception as e:
                logger.error(f"Failed to log trade open: {str(e)}", extra={**error_context, "position_id": position.id})
            
            # 12. Send notification hooks (non-blocking)
            try:
                # Legacy hook (for backward compatibility)
                notify_trade_opened(position, account)
                # Flutter hook (structured payload)
                on_trade_open(position, account, entry_price)
            except Exception as e:
                logger.error(f"Failed to send notification: {str(e)}", extra={**error_context, "position_id": position.id})
            
            logger.info(f"Trade opened successfully: position_id={position.id}", extra={**error_context, "position_id": position.id})
            return position
    
    except (TradeValidationError, MarketDataError, RiskLimitError) as e:
        # Re-raise custom exceptions (already logged)
        raise
    except Exception as e:
        # Catch any unexpected errors
        logger.error(
            f"Unexpected error opening trade: {str(e)}",
            extra={**error_context, "error_type": type(e).__name__},
            exc_info=True
        )
        # Transaction will rollback automatically
        raise TradeValidationError(
            f"Unexpected error opening trade: {str(e)}",
            details={**error_context, "error_type": type(e).__name__, "error_message": str(e)}
        )
