"""
Ultra Calm Mode - Risk Policy Framework
Mode works as risk policy, not hardcoded in trade logic.
"""
from decimal import Decimal
from typing import Dict, Any
from common.constants import RiskLimits


class UltraCalmMode:
    """
    Ultra Calm mode risk policy.
    Configurable via settings, not hardcoded in trade logic.
    """
    
    # Risk limits for Ultra Calm mode
    MAX_RISK_PERCENT = Decimal("1.0")  # 1% max risk per trade
    MAX_DAILY_LOSS_PERCENT = Decimal("2.0")  # 2% max daily loss
    MAX_POSITION_SIZE_PERCENT = Decimal("10.0")  # 10% max position size
    REQUIRED_STOP_LOSS = True  # Stop loss is mandatory
    REQUIRED_TAKE_PROFIT = False  # Take profit is optional
    
    # Stress-free flag for PnL display
    STRESS_FREE_MODE = True  # Blur PnL in UI
    
    @classmethod
    def get_risk_config(cls) -> Dict[str, Any]:
        """
        Get risk configuration for Ultra Calm mode.
        This can be loaded from settings/database.
        """
        return {
            "max_risk_percent": float(cls.MAX_RISK_PERCENT),
            "max_daily_loss_percent": float(cls.MAX_DAILY_LOSS_PERCENT),
            "max_position_size_percent": float(cls.MAX_POSITION_SIZE_PERCENT),
            "required_stop_loss": cls.REQUIRED_STOP_LOSS,
            "required_take_profit": cls.REQUIRED_TAKE_PROFIT,
            "stress_free_mode": cls.STRESS_FREE_MODE,
        }
    
    @classmethod
    def validate_risk(cls, risk_percent: Decimal, position_size_percent: Decimal) -> bool:
        """
        Validate risk parameters against Ultra Calm limits.
        
        Args:
            risk_percent: Risk percentage
            position_size_percent: Position size as % of balance
        
        Returns:
            True if valid, raises ValueError if invalid
        """
        if risk_percent > cls.MAX_RISK_PERCENT:
            raise ValueError(
                f"Ultra Calm mode: Max risk is {cls.MAX_RISK_PERCENT}%, got {risk_percent}%"
            )
        
        if position_size_percent > cls.MAX_POSITION_SIZE_PERCENT:
            raise ValueError(
                f"Ultra Calm mode: Max position size is {cls.MAX_POSITION_SIZE_PERCENT}%, got {position_size_percent}%"
            )
        
        return True
    
    @classmethod
    def is_stress_free(cls) -> bool:
        """Check if stress-free mode is enabled (for PnL display)"""
        return cls.STRESS_FREE_MODE
