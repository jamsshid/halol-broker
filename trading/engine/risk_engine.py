"""
Order Validation Engine (CORE ENGINE)
Enforces trading rules: SL mandatory, TP optional, risk validation, SL distance check.
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from trading.models import Position, TradeAccount, Instrument


class OrderValidationError(ValidationError):
    """Custom validation error for order validation"""
    pass


class RiskEngine:
    """
    Core order validation engine.
    Order validation enforced (SL mandatory, TP optional, risk checked).
    """
    
    @staticmethod
    def validate_stop_loss_mandatory(stop_loss, side, entry_price):
        """
        Validate that Stop Loss is mandatory and correctly positioned.
        
        Args:
            stop_loss: Stop loss price (must not be None)
            side: 'BUY' or 'SELL'
            entry_price: Entry price
        
        Raises:
            OrderValidationError: If SL is missing or invalid
        """
        # Order validation enforced (SL mandatory, TP optional, risk checked)
        if stop_loss is None:
            raise OrderValidationError(
                "Stop Loss is mandatory. Please provide a stop loss price."
            )
        
        # Validate SL direction
        if side == Position.Side.BUY:
            if stop_loss >= entry_price:
                raise OrderValidationError(
                    f"For BUY orders, stop loss ({stop_loss}) must be below entry price ({entry_price})"
                )
        elif side == Position.Side.SELL:
            if stop_loss <= entry_price:
                raise OrderValidationError(
                    f"For SELL orders, stop loss ({stop_loss}) must be above entry price ({entry_price})"
                )
    
    @staticmethod
    def validate_take_profit_optional(take_profit, side, entry_price):
        """
        Validate Take Profit if provided (optional).
        
        Args:
            take_profit: Take profit price (can be None)
            side: 'BUY' or 'SELL'
            entry_price: Entry price
        
        Raises:
            OrderValidationError: If TP is invalid (if provided)
        """
        # Take Profit is optional - only validate if provided
        if take_profit is not None:
            if side == Position.Side.BUY:
                if take_profit <= entry_price:
                    raise OrderValidationError(
                        f"For BUY orders, take profit ({take_profit}) must be above entry price ({entry_price})"
                    )
            elif side == Position.Side.SELL:
                if take_profit >= entry_price:
                    raise OrderValidationError(
                        f"For SELL orders, take profit ({take_profit}) must be below entry price ({entry_price})"
                    )
    
    @staticmethod
    def validate_risk_percent(risk_percent, account: TradeAccount):
        """
        Validate risk percentage against account limits.
        
        Args:
            risk_percent: Risk percentage (float)
            account: TradeAccount instance
        
        Raises:
            OrderValidationError: If risk is invalid
        """
        # Order validation enforced (SL mandatory, TP optional, risk checked)
        if risk_percent <= 0:
            raise OrderValidationError(
                f"Risk percentage must be positive, got {risk_percent}%"
            )
        
        if risk_percent > account.max_risk_per_trade:
            raise OrderValidationError(
                f"Risk percentage ({risk_percent}%) exceeds maximum allowed "
                f"({account.max_risk_per_trade}%) for this account"
            )
    
    @staticmethod
    def validate_sl_distance(stop_loss, entry_price, instrument: Instrument):
        """
        Validate Stop Loss distance meets minimum requirement.
        
        Args:
            stop_loss: Stop loss price
            entry_price: Entry price
            instrument: Instrument instance
        
        Raises:
            OrderValidationError: If SL distance is too small
        """
        # Order validation enforced (SL mandatory, TP optional, risk checked)
        stop_distance = abs(entry_price - stop_loss)
        
        if stop_distance < instrument.min_stop_distance:
            raise OrderValidationError(
                f"Stop loss distance ({stop_distance}) is below minimum required "
                f"({instrument.min_stop_distance}) for instrument {instrument.symbol}"
            )
    
    @staticmethod
    def validate_order(
        account: TradeAccount,
        instrument: Instrument,
        side: str,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal = None,
        risk_percent: float = None
    ):
        """
        Complete order validation (all checks).
        
        Args:
            account: TradeAccount instance
            instrument: Instrument instance
            side: 'BUY' or 'SELL'
            entry_price: Entry price
            stop_loss: Stop loss price (MANDATORY)
            take_profit: Take profit price (OPTIONAL)
            risk_percent: Risk percentage
        
        Raises:
            OrderValidationError: If validation fails
        """
        # Order validation enforced (SL mandatory, TP optional, risk checked)
        
        # 1. Stop Loss mandatory check
        RiskEngine.validate_stop_loss_mandatory(stop_loss, side, entry_price)
        
        # 2. Take Profit optional check (only if provided)
        RiskEngine.validate_take_profit_optional(take_profit, side, entry_price)
        
        # 3. Risk percent validation
        if risk_percent is not None:
            RiskEngine.validate_risk_percent(risk_percent, account)
        
        # 4. SL distance validation
        RiskEngine.validate_sl_distance(stop_loss, entry_price, instrument)
        
        return True
