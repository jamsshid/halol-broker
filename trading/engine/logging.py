"""
Trade History Logging Engine
Logs all trade lifecycle events (OPEN, CLOSE, SL_HIT, TP_HIT, PARTIAL).
"""
from decimal import Decimal
from typing import Optional, Dict, Any
from django.utils import timezone
from trading.models import Position, PositionLog
from common.enums import TradeEvent


class TradeLogger:
    """Trade event logging engine"""
    
    @staticmethod
    def log_event(
        position: Position,
        event_type: str,
        price: Optional[Decimal] = None,
        size: Optional[Decimal] = None,
        pnl: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PositionLog:
        """
        Log a trade event.
        
        Args:
            position: Position instance
            event_type: TradeEvent value (OPEN, CLOSE, SL_HIT, TP_HIT, PARTIAL)
            price: Price at event
            size: Size affected (for partial close)
            pnl: PnL at this event
            metadata: Additional event data
        
        Returns:
            PositionLog instance
        """
        log = PositionLog.objects.create(
            position=position,
            event_type=event_type,
            price=price,
            size=size,
            pnl=pnl,
            metadata=metadata or {}
        )
        return log
    
    @staticmethod
    def log_open(position: Position, entry_price: Decimal) -> PositionLog:
        """Log position open event"""
        return TradeLogger.log_event(
            position=position,
            event_type=TradeEvent.OPEN,
            price=entry_price,
            size=position.position_size,
            metadata={
                "side": position.side,
                "mode": position.mode,
                "stop_loss": str(position.stop_loss),
                "take_profit": str(position.take_profit) if position.take_profit else None,
                "risk_percent": position.risk_percent,
            }
        )
    
    @staticmethod
    def log_close(
        position: Position,
        closing_price: Decimal,
        pnl: Decimal,
        close_size: Optional[Decimal] = None
    ) -> PositionLog:
        """Log position close event"""
        is_partial = close_size is not None and close_size < position.position_size
        
        return TradeLogger.log_event(
            position=position,
            event_type=TradeEvent.PARTIAL if is_partial else TradeEvent.CLOSE,
            price=closing_price,
            size=close_size or position.position_size,
            pnl=pnl,
            metadata={
                "remaining_size": str(position.remaining_size) if position.remaining_size else "0",
                "is_partial": is_partial,
            }
        )
    
    @staticmethod
    def log_sl_hit(position: Position, price: Decimal, pnl: Decimal) -> PositionLog:
        """Log stop loss hit event"""
        return TradeLogger.log_event(
            position=position,
            event_type=TradeEvent.SL_HIT,
            price=price,
            pnl=pnl,
            metadata={
                "stop_loss": str(position.stop_loss),
            }
        )
    
    @staticmethod
    def log_tp_hit(position: Position, price: Decimal, pnl: Decimal) -> PositionLog:
        """Log take profit hit event"""
        return TradeLogger.log_event(
            position=position,
            event_type=TradeEvent.TP_HIT,
            price=price,
            pnl=pnl,
            metadata={
                "take_profit": str(position.take_profit),
            }
        )
