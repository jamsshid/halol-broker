from decimal import Decimal
import logging
from django.utils import timezone
from django.db import transaction
from trading.models import Position
from trading.engine.pnl_engine import PnLEngine
from trading.engine.logging import TradeLogger
from trading.services.pnl_sync import PnLSyncService
from common.signals import balance_updated
from common.hooks import notify_trade_closed, notify_sl_hit, notify_tp_hit
from trading.hooks import on_trade_close, on_sl_hit, on_tp_hit
from common.exceptions import TradeValidationError, MarketDataError
from common.constants import TradingConstants
from calm.helpers import send_pnl_adjustment_signal

logger = logging.getLogger(__name__)


def close_trade(
    *,
    position_id,
    closing_price,
    close_size=None,  # None = full close, Decimal = partial close
    backend_client=None,  # Optional injection for Backend-2 mock in tests
):
    """
    Close a trade position (full or partial) with full error handling and rollback logic.
    
    Args:
        position_id: Position ID
        closing_price: Closing price
        close_size: Size to close (None = full close)
    
    Returns:
        Position instance (updated)
    
    Raises:
        TradeValidationError: If trade validation fails
        MarketDataError: If market data is unavailable
    """
    error_context = {
        "position_id": position_id,
        "closing_price": str(closing_price) if closing_price else None,
        "close_size": str(close_size) if close_size else None,
    }
    
    try:
        with transaction.atomic():
            # 1. Get position with lock (prevents concurrent modifications)
            try:
                position = Position.objects.select_for_update().get(
                    id=position_id,
                    status__in=[Position.Status.OPEN, Position.Status.PARTIAL]
                )
                error_context.update({
                    "user_id": position.account.user.id if position.account.user else None,
                    "account_id": position.account.id,
                    "instrument": position.instrument.symbol,
                    "current_status": position.status,
                })
            except Position.DoesNotExist:
                logger.warning(f"Position {position_id} not found or not open", extra=error_context)
                raise TradeValidationError(
                    f"Open position {position_id} not found",
                    details=error_context
                )
            
            # 2. Prevent double close
            if position.status == Position.Status.CLOSED:
                logger.warning(f"Position {position_id} is already closed", extra=error_context)
                raise TradeValidationError(
                    f"Position {position_id} is already closed",
                    details=error_context
                )
            
            # 3. Validate closing price
            if closing_price is None or closing_price <= 0:
                logger.warning(f"Invalid closing price: {closing_price}", extra=error_context)
                raise MarketDataError(
                    f"Invalid closing price: {closing_price}",
                    details=error_context
                )
            
            # 4. Determine close size
            remaining_before = position.remaining_size or position.position_size
            if close_size is None:
                # Full close
                close_size = remaining_before
            else:
                # Partial close validation
                if close_size <= 0:
                    logger.warning(f"Close size must be positive: {close_size}", extra=error_context)
                    raise TradeValidationError(
                        f"Close size must be positive. Minimum: {TradingConstants.PARTIAL_CLOSE_MIN_SIZE}, got: {close_size}",
                        details={**error_context, "min_close_size": str(TradingConstants.PARTIAL_CLOSE_MIN_SIZE)}
                    )
                if close_size < TradingConstants.PARTIAL_CLOSE_MIN_SIZE:
                    logger.warning(f"Close size below minimum: {close_size}", extra=error_context)
                    raise TradeValidationError(
                        f"Close size is below minimum required: {TradingConstants.PARTIAL_CLOSE_MIN_SIZE}",
                        details={**error_context, "min_close_size": str(TradingConstants.PARTIAL_CLOSE_MIN_SIZE)}
                    )
                if close_size > remaining_before:
                    logger.warning(
                        f"Close size {close_size} exceeds remaining {remaining_before}",
                        extra=error_context
                    )
                    raise TradeValidationError(
                        f"Cannot close more than remaining position size. Close size: {close_size}, Remaining: {remaining_before}",
                        details={**error_context, "remaining_size": str(remaining_before)}
                    )
            
            # 5. Calculate remaining size (before PnL calculation)
            remaining_size = remaining_before - close_size
            
            # 6. Calculate PnL (do not mutate yet)
            try:
                realized_pnl = PnLEngine.calculate_pnl(position, closing_price, close_size)
            except Exception as e:
                logger.error(f"PnL calculation failed: {str(e)}", extra=error_context, exc_info=True)
                raise TradeValidationError(
                    f"PnL calculation failed: {str(e)}",
                    details={**error_context, "pnl_error": str(e)}
                )

            # 6.1 Sync with Backend-2 (for real accounts). Rollback on mismatch/error.
            if position.account.account_type != "demo":
                sync_service = PnLSyncService(backend_client=backend_client)
                try:
                    sync_service.sync_realized_pnl(position, realized_pnl)
                except Exception as e:
                    logger.error(
                        f"PnL sync failed: {str(e)}",
                        extra={**error_context, "position_id": position.id},
                        exc_info=True,
                    )
                    raise
            
            # 7. Check if SL/TP hit
            is_sl_hit = False
            is_tp_hit = False
            
            if position.side == Position.Side.BUY:
                is_sl_hit = closing_price <= position.stop_loss
                is_tp_hit = position.take_profit and closing_price >= position.take_profit
            else:  # SELL
                is_sl_hit = closing_price >= position.stop_loss
                is_tp_hit = position.take_profit and closing_price <= position.take_profit
            
            # 8. Apply PnL after successful sync (mutates position)
            PnLEngine.apply_close_pnl(position, closing_price, close_size)

            # 9. Update position status (atomic update)
            # If this fails, transaction will rollback automatically
            if remaining_size <= TradingConstants.FULL_CLOSE_THRESHOLD:  # Full close
                position.status = Position.Status.CLOSED
                position.closed_at = timezone.now()
                position.remaining_size = Decimal("0")
            else:
                position.status = Position.Status.PARTIAL
                position.remaining_size = remaining_size
            
            # 10. Save position (atomic)
            position.save()
            
            # 11. Log trade event (outside transaction to avoid rollback)
            # If logging fails, we still want the position updated
            try:
                if is_sl_hit:
                    TradeLogger.log_sl_hit(position, closing_price, realized_pnl)
                elif is_tp_hit:
                    TradeLogger.log_tp_hit(position, closing_price, realized_pnl)
                else:
                    TradeLogger.log_close(position, closing_price, realized_pnl, close_size)
            except Exception as e:
                logger.error(f"Failed to log trade close: {str(e)}", extra={**error_context, "position_id": position.id})
            
            # 12. Send notifications (non-blocking)
            try:
                if is_sl_hit:
                    # Legacy hook
                    notify_sl_hit(position, position.account, realized_pnl)
                    # Flutter hook
                    on_sl_hit(position, position.account, closing_price, realized_pnl)
                elif is_tp_hit:
                    # Legacy hook
                    notify_tp_hit(position, position.account, realized_pnl)
                    # Flutter hook
                    on_tp_hit(position, position.account, closing_price, realized_pnl)
                else:
                    # Legacy hook
                    notify_trade_closed(position, position.account, realized_pnl)
                    # Flutter hook
                    on_trade_close(position, position.account, closing_price, realized_pnl, close_size)
            except Exception as e:
                logger.error(f"Failed to send notification: {str(e)}", extra={**error_context, "position_id": position.id})
            
            # 13. Send signal for balance update hook (non-blocking)
            try:
                balance_updated.send(
                    sender=Position,
                    account=position.account,
                    position=position,
                    close_size=close_size,
                    closing_price=closing_price,
                    pnl=realized_pnl
                )
            except Exception as e:
                logger.error(f"Failed to send balance update signal: {str(e)}", extra={**error_context, "position_id": position.id})
            
            # 14. Send mode-based PnL adjustment signal (non-blocking)
            try:
                send_pnl_adjustment_signal(position, realized_pnl)
            except Exception as e:
                logger.error(f"Failed to send PnL adjustment signal: {str(e)}", extra={**error_context, "position_id": position.id})

            # 15. Clear Redis calm state if position is fully closed (non-blocking)
            if position.status == Position.Status.CLOSED:
                try:
                    from calm.helpers import clear_calm_state_on_close
                    clear_calm_state_on_close(position.id)
                except Exception as e:
                    logger.error(f"Failed to clear calm state: {str(e)}", extra={**error_context, "position_id": position.id})

            logger.info(
                f"Trade closed successfully: position_id={position.id}, pnl={realized_pnl}, status={position.status}",
                extra={**error_context, "position_id": position.id, "realized_pnl": str(realized_pnl), "final_status": position.status}
            )
            return position
    
    except (TradeValidationError, MarketDataError) as e:
        # Re-raise custom exceptions (already logged)
        raise
    except Exception as e:
        # Catch any unexpected errors
        logger.error(
            f"Unexpected error closing trade: {str(e)}",
            extra={**error_context, "error_type": type(e).__name__},
            exc_info=True
        )
        # Transaction will rollback automatically
        raise TradeValidationError(
            f"Unexpected error closing trade: {str(e)}",
            details={**error_context, "error_type": type(e).__name__, "error_message": str(e)}
        )
