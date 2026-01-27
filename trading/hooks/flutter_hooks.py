"""
Flutter Trade Event Hooks
Structured event hooks for Flutter mobile app integration.
Each hook provides a consistent payload structure for frontend consumption.
"""
import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from django.utils import timezone

from trading.models import Position, TradeAccount
from common.hooks import notify

logger = logging.getLogger(__name__)


def _build_base_payload(position: Position, account: TradeAccount) -> Dict[str, Any]:
    """Build base payload structure for all trade events"""
    return {
        "position_id": str(position.id),
        "account_id": str(account.id),
        "user_id": account.user.id if account.user else None,
        "symbol": position.instrument.symbol,
        "side": position.side,
        "mode": position.mode,
        "timestamp": timezone.now().isoformat(),
    }


def on_trade_open(position: Position, account: TradeAccount, entry_price: Decimal) -> Dict[str, Any]:
    """
    Hook called when a trade is opened.
    
    Args:
        position: Position instance
        account: TradeAccount instance
        entry_price: Entry price
    
    Returns:
        dict: Flutter-friendly payload
    """
    payload = {
        **_build_base_payload(position, account),
        "event_type": "TRADE_OPENED",
        "entry_price": str(entry_price),
        "stop_loss": str(position.stop_loss),
        "take_profit": str(position.take_profit) if position.take_profit else None,
        "position_size": str(position.position_size),
        "risk_percent": float(position.risk_percent),
        "timeframe": position.timeframe,
        "status": position.status,
    }
    
    # Log for debugging
    logger.info(
        f"Trade opened: position_id={position.id}, symbol={position.instrument.symbol}",
        extra={"payload": payload}
    )
    
    # Send notification (placeholder for Flutter push notification)
    notify(
        event_type="TRADE_OPENED",
        payload=payload,
        user_id=account.user.id if account.user else None
    )
    
    return payload


def on_trade_close(
    position: Position,
    account: TradeAccount,
    closing_price: Decimal,
    pnl: Decimal,
    close_size: Optional[Decimal] = None
) -> Dict[str, Any]:
    """
    Hook called when a trade is closed.
    
    Args:
        position: Position instance
        account: TradeAccount instance
        closing_price: Closing price
        pnl: Realized PnL
        close_size: Size closed (None = full close)
    
    Returns:
        dict: Flutter-friendly payload
    """
    payload = {
        **_build_base_payload(position, account),
        "event_type": "TRADE_CLOSED",
        "closing_price": str(closing_price),
        "pnl": str(pnl),
        "close_size": str(close_size) if close_size else str(position.position_size),
        "remaining_size": str(position.remaining_size or Decimal("0")),
        "status": position.status,
        "is_partial": position.status == Position.Status.PARTIAL,
    }
    
    logger.info(
        f"Trade closed: position_id={position.id}, pnl={pnl}",
        extra={"payload": payload}
    )
    
    notify(
        event_type="TRADE_CLOSED",
        payload=payload,
        user_id=account.user.id if account.user else None
    )
    
    return payload


def on_sl_hit(
    position: Position,
    account: TradeAccount,
    closing_price: Decimal,
    pnl: Decimal
) -> Dict[str, Any]:
    """
    Hook called when Stop Loss is hit.
    
    Args:
        position: Position instance
        account: TradeAccount instance
        closing_price: Price at which SL was hit
        pnl: Realized PnL (usually negative)
    
    Returns:
        dict: Flutter-friendly payload
    """
    payload = {
        **_build_base_payload(position, account),
        "event_type": "SL_HIT",
        "closing_price": str(closing_price),
        "stop_loss": str(position.stop_loss),
        "pnl": str(pnl),
        "status": position.status,
    }
    
    logger.warning(
        f"Stop Loss hit: position_id={position.id}, pnl={pnl}",
        extra={"payload": payload}
    )
    
    notify(
        event_type="SL_HIT",
        payload=payload,
        user_id=account.user.id if account.user else None
    )
    
    return payload


def on_tp_hit(
    position: Position,
    account: TradeAccount,
    closing_price: Decimal,
    pnl: Decimal
) -> Dict[str, Any]:
    """
    Hook called when Take Profit is hit.
    
    Args:
        position: Position instance
        account: TradeAccount instance
        closing_price: Price at which TP was hit
        pnl: Realized PnL (usually positive)
    
    Returns:
        dict: Flutter-friendly payload
    """
    payload = {
        **_build_base_payload(position, account),
        "event_type": "TP_HIT",
        "closing_price": str(closing_price),
        "take_profit": str(position.take_profit) if position.take_profit else None,
        "pnl": str(pnl),
        "status": position.status,
    }
    
    logger.info(
        f"Take Profit hit: position_id={position.id}, pnl={pnl}",
        extra={"payload": payload}
    )
    
    notify(
        event_type="TP_HIT",
        payload=payload,
        user_id=account.user.id if account.user else None
    )
    
    return payload


def on_pnl_update(
    position: Position,
    account: TradeAccount,
    unrealized_pnl: Decimal,
    current_price: Decimal
) -> Dict[str, Any]:
    """
    Hook called when unrealized PnL is updated (real-time updates).
    
    Args:
        position: Position instance
        account: TradeAccount instance
        unrealized_pnl: Current unrealized PnL
        current_price: Current market price
    
    Returns:
        dict: Flutter-friendly payload
    """
    payload = {
        **_build_base_payload(position, account),
        "event_type": "PNL_UPDATE",
        "unrealized_pnl": str(unrealized_pnl),
        "current_price": str(current_price),
        "entry_price": str(position.entry_price),
        "pnl_percent": str((unrealized_pnl / (position.position_size * position.entry_price)) * 100) if position.position_size > 0 else "0",
    }
    
    # Only log significant PnL changes to avoid spam
    if abs(unrealized_pnl) > Decimal("10.00"):
        logger.debug(
            f"PnL update: position_id={position.id}, unrealized_pnl={unrealized_pnl}",
            extra={"payload": payload}
        )
    
    notify(
        event_type="PNL_UPDATE",
        payload=payload,
        user_id=account.user.id if account.user else None
    )
    
    return payload


def on_calm_mode_feedback(
    position: Position,
    account: TradeAccount,
    mode: str,
    feedback_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Hook called for Calm mode feedback (Ultra/Semi mode adjustments).
    
    Args:
        position: Position instance
        account: TradeAccount instance
        mode: Calm mode ('ULTRA' or 'SEMI')
        feedback_data: Additional mode-specific data
    
    Returns:
        dict: Flutter-friendly payload
    """
    payload = {
        **_build_base_payload(position, account),
        "event_type": "CALM_MODE_FEEDBACK",
        "mode": mode,
        "feedback": feedback_data,
    }
    
    logger.info(
        f"Calm mode feedback: position_id={position.id}, mode={mode}",
        extra={"payload": payload}
    )
    
    notify(
        event_type="CALM_MODE_FEEDBACK",
        payload=payload,
        user_id=account.user.id if account.user else None
    )
    
    return payload
