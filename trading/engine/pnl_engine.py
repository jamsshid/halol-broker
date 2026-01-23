"""
PnL Calculation Engine
Handles Buy/Sell PnL, Unrealized/Realized separation, Partial close support.
"""
from decimal import Decimal
from typing import Optional
from django.utils import timezone
from trading.models import Position


class PnLEngine:
    """PnL calculation engine"""
    
    @staticmethod
    def calculate_pnl(
        position: Position,
        current_price: Decimal,
        close_size: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate PnL for a position.
        
        Args:
            position: Position instance
            current_price: Current market price
            close_size: Size being closed (None = full position)
        
        Returns:
            PnL amount (Decimal)
        """
        entry_price = position.entry_price
        position_size = close_size or (position.remaining_size or position.position_size)
        side = position.side
        
        # Calculate PnL based on side
        if side == Position.Side.BUY:
            pnl = (current_price - entry_price) * position_size
        elif side == Position.Side.SELL:
            pnl = (entry_price - current_price) * position_size
        else:
            raise ValueError(f"Invalid position side: {side}")
        
        return pnl.quantize(Decimal("0.01"))
    
    @staticmethod
    def calculate_unrealized_pnl(position: Position, current_price: Decimal) -> Decimal:
        """
        Calculate unrealized PnL for open position.
        
        Args:
            position: Position instance (must be OPEN or PARTIAL)
            current_price: Current market price
        
        Returns:
            Unrealized PnL (Decimal)
        """
        if position.status == Position.Status.CLOSED:
            return Decimal("0.00")
        
        remaining_size = position.remaining_size or position.position_size
        return PnLEngine.calculate_pnl(position, current_price, remaining_size)
    
    @staticmethod
    def calculate_realized_pnl(position: Position, closing_price: Decimal) -> Decimal:
        """
        Calculate realized PnL when closing.
        
        Args:
            position: Position instance
            closing_price: Closing price
        
        Returns:
            Realized PnL (Decimal)
        """
        # For full close, use full position size
        # For partial close, use closed size (position_size - remaining_size)
        if position.status == Position.Status.CLOSED:
            # Already closed - use full size
            closed_size = position.position_size
        else:
            # Partial close - calculate closed size
            closed_size = position.position_size - (position.remaining_size or Decimal("0"))
        
        return PnLEngine.calculate_pnl(position, closing_price, closed_size)
    
    @staticmethod
    def update_position_pnl(position: Position, current_price: Decimal):
        """
        Update position's unrealized PnL.
        
        Args:
            position: Position instance
            current_price: Current market price
        """
        if position.status == Position.Status.CLOSED:
            return
        
        unrealized_pnl = PnLEngine.calculate_unrealized_pnl(position, current_price)
        position.unrealized_pnl = unrealized_pnl
        position.save(update_fields=["unrealized_pnl"])
    
    @staticmethod
    def apply_close_pnl(
        position: Position,
        closing_price: Decimal,
        close_size: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate and apply PnL for closing trade.
        
        Args:
            position: Position instance
            closing_price: Closing price
            close_size: Size being closed (None = full)
        
        Returns:
            Realized PnL amount
        """
        if close_size is None:
            close_size = position.remaining_size or position.position_size
        
        realized_pnl = PnLEngine.calculate_pnl(position, closing_price, close_size)
        
        # Update position PnL
        if position.pnl is None:
            position.pnl = Decimal("0.00")
        
        position.pnl += realized_pnl
        position.unrealized_pnl = None  # Clear unrealized after close
        position.save(update_fields=["pnl", "unrealized_pnl"])
        
        return realized_pnl
