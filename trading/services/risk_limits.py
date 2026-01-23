"""
Risk enforcement service aligning Backend-1 with Backend-2 limits (mocked).
Checks: daily max loss, per-trade risk %, leverage (delegated elsewhere), mode impact.
"""
from decimal import Decimal
from typing import Optional

from common.exceptions import RiskLimitError


class LimitServiceClientInterface:
    """Interface for Backend-2 limit service (mockable)."""

    def get_daily_loss_current(self, account_id) -> Decimal:
        raise NotImplementedError


class MockLimitServiceClient(LimitServiceClientInterface):
    """In-memory mock limit service for tests."""

    def __init__(self):
        self._daily_loss = {}

    def set_daily_loss(self, account_id, value: Decimal):
        self._daily_loss[account_id] = Decimal(str(value))

    def get_daily_loss_current(self, account_id) -> Decimal:
        return self._daily_loss.get(account_id, Decimal("0.00"))


class RiskGuard:
    """Risk enforcement helper."""

    def __init__(self, limit_client: Optional[LimitServiceClientInterface] = None):
        self.limit_client = limit_client or MockLimitServiceClient()

    def enforce(
        self,
        *,
        account,
        risk_percent: Decimal,
        mode: Optional[str] = None,
    ):
        """
        Enforce risk rules:
        - Max risk per trade (%)
        - Daily max loss (% of balance)
        - Mode-aware tolerance (Ultra tighter than Semi by design in mode policy)
        """
        # 1) Max risk per trade
        if risk_percent > Decimal(str(account.max_risk_per_trade)):
            raise RiskLimitError(
                f"Risk per trade {risk_percent}% exceeds limit {account.max_risk_per_trade}%",
                details={"account_id": account.id, "risk_percent": str(risk_percent)},
            )

        # 2) Daily max loss check (Backend-2 mimic)
        daily_loss_current = self.limit_client.get_daily_loss_current(account.id)
        max_daily_loss_percent = Decimal(str(account.max_daily_loss or 0))
        if max_daily_loss_percent > 0:
            max_daily_loss_amount = (Decimal(str(account.balance)) * max_daily_loss_percent) / Decimal(
                "100"
            )
            # Approximate potential additional loss = risk% * balance
            potential_loss = (Decimal(str(account.balance)) * risk_percent) / Decimal("100")
            if (daily_loss_current + potential_loss) > max_daily_loss_amount:
                raise RiskLimitError(
                    "Daily loss limit exceeded",
                    details={
                        "account_id": account.id,
                        "daily_loss_current": str(daily_loss_current),
                        "potential_loss": str(potential_loss),
                        "max_daily_loss_amount": str(max_daily_loss_amount),
                    },
                )

        # 3) Mode effect handled by mode policy (Ultra/Semi) elsewhere
        return True
