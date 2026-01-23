"""
Trade Notifications & Hooks
Interface for trade event notifications (Future: Firebase, WebSocket).
Currently returns backend signals only.
"""
from typing import Dict, Any, Optional
from django.dispatch import Signal


# Notification signal
trade_notification = Signal()  # providing_args=['event_type', 'payload', 'user_id']


def notify(event_type: str, payload: Dict[str, Any], user_id: Optional[int] = None):
    """
    Send trade event notification.
    
    This is a placeholder interface for future push notifications.
    Currently sends Django signal only.
    
    Future implementations:
    - Firebase Cloud Messaging (FCM) for mobile
    - WebSocket for real-time updates
    - Email notifications
    
    Args:
        event_type: Event type (e.g., 'TRADE_OPENED', 'TRADE_CLOSED', 'SL_HIT', 'TP_HIT')
        payload: Notification payload
        user_id: User ID (optional, can be extracted from payload)
    
    Returns:
        None (sends signal)
    """
    # Extract user_id from payload if not provided
    if user_id is None:
        user_id = payload.get("user_id") or payload.get("account", {}).get("user_id")
    
    # Send Django signal (backend only)
    trade_notification.send(
        sender=None,
        event_type=event_type,
        payload=payload,
        user_id=user_id
    )
    
    # Future: Add Firebase/WebSocket here
    # Example:
    # if settings.ENABLE_PUSH_NOTIFICATIONS:
    #     send_fcm_notification(user_id, event_type, payload)
    # if settings.ENABLE_WEBSOCKET:
    #     send_websocket_message(user_id, event_type, payload)


def notify_trade_opened(position, account):
    """Notify trade opened event"""
    notify(
        event_type="TRADE_OPENED",
        payload={
            "position_id": position.id,
            "symbol": position.instrument.symbol,
            "side": position.side,
            "entry_price": str(position.entry_price),
            "account_id": account.id,
            "user_id": account.user.id,
        }
    )


def notify_trade_closed(position, account, pnl):
    """Notify trade closed event"""
    notify(
        event_type="TRADE_CLOSED",
        payload={
            "position_id": position.id,
            "symbol": position.instrument.symbol,
            "status": position.status,
            "pnl": str(pnl),
            "account_id": account.id,
            "user_id": account.user.id,
        }
    )


def notify_sl_hit(position, account, pnl):
    """Notify stop loss hit event"""
    notify(
        event_type="SL_HIT",
        payload={
            "position_id": position.id,
            "symbol": position.instrument.symbol,
            "stop_loss": str(position.stop_loss),
            "pnl": str(pnl),
            "account_id": account.id,
            "user_id": account.user.id,
        }
    )


def notify_tp_hit(position, account, pnl):
    """Notify take profit hit event"""
    notify(
        event_type="TP_HIT",
        payload={
            "position_id": position.id,
            "symbol": position.instrument.symbol,
            "take_profit": str(position.take_profit),
            "pnl": str(pnl),
            "account_id": account.id,
            "user_id": account.user.id,
        }
    )
