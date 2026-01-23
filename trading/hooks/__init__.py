"""
Flutter Trade Event Hooks
Event-based hooks for Flutter mobile app integration.
Provides structured payloads for real-time trade updates.
"""
from .flutter_hooks import (
    on_trade_open,
    on_trade_close,
    on_sl_hit,
    on_tp_hit,
    on_pnl_update,
    on_calm_mode_feedback,
)

__all__ = [
    "on_trade_open",
    "on_trade_close",
    "on_sl_hit",
    "on_tp_hit",
    "on_pnl_update",
    "on_calm_mode_feedback",
]
