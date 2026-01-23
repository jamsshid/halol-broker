"""
PnL sync between Backend-1 (trading) and Backend-2 (wallet).
Uses a mockable Backend-2 client to validate PnL consistency.
"""
from decimal import Decimal
from typing import Optional

from django.db import transaction

from common.exceptions import TradeValidationError


class Backend2ClientInterface:
    """Interface for Backend-2 client. Can be replaced with real API adapter later."""

    def apply_pnl(self, account_ref, pnl_amount: Decimal, trade_id) -> Decimal:
        """Apply PnL on Backend-2 side and return the amount applied."""
        raise NotImplementedError


class MockBackend2Client(Backend2ClientInterface):
    """Default mock client: echoes back the same PnL."""

    def __init__(self):
        self.calls = []

    def apply_pnl(self, account_ref, pnl_amount: Decimal, trade_id) -> Decimal:
        self.calls.append(
            {"account_ref": account_ref, "pnl": Decimal(pnl_amount), "trade_id": trade_id}
        )
        return Decimal(pnl_amount)


class MismatchBackend2Client(Backend2ClientInterface):
    """Test helper to simulate mismatch between Backend-1 and Backend-2."""

    def __init__(self, delta: Decimal = Decimal("1.00")):
        self.delta = delta

    def apply_pnl(self, account_ref, pnl_amount: Decimal, trade_id) -> Decimal:
        return Decimal(pnl_amount) + self.delta


class PnLSyncService:
    """Sync PnL with Backend-2 and ensure consistency."""

    def __init__(self, backend_client: Optional[Backend2ClientInterface] = None):
        self.backend_client = backend_client or MockBackend2Client()

    @transaction.atomic
    def sync_realized_pnl(self, position, realized_pnl: Decimal) -> Decimal:
        """
        Send realized PnL to Backend-2 and ensure amounts match.
        Raises TradeValidationError on mismatch.
        """
        backend_pnl = self.backend_client.apply_pnl(
            account_ref=position.account.id,
            pnl_amount=realized_pnl,
            trade_id=position.id,
        )

        backend_pnl = Decimal(str(backend_pnl))
        realized_pnl = Decimal(str(realized_pnl))

        if backend_pnl != realized_pnl:
            raise TradeValidationError(
                f"PnL mismatch between trading ({realized_pnl}) and backend-2 ({backend_pnl})",
                details={
                    "position_id": position.id,
                    "account_id": position.account.id,
                    "backend_pnl": str(backend_pnl),
                    "trading_pnl": str(realized_pnl),
                },
            )

        return backend_pnl
