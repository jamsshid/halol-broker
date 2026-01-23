"""
Demo account lifecycle utilities (no impact on real accounts/wallets).
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from common.exceptions import SecurityException, TradeValidationError
from trading.models import Position, TradeAccount


DEFAULT_DEMO_BALANCE = Decimal("10000.00")


@transaction.atomic
def reset_demo_account(account: TradeAccount, default_balance: Decimal = DEFAULT_DEMO_BALANCE):
    """
    Reset demo account:
    - Close all open/partial positions
    - Reset balance to default
    - Preserve history/logs
    """
    if account.account_type != "demo":
        raise SecurityException("Reset allowed only for demo accounts")

    # Close positions logically (no PnL application to real wallet)
    now = timezone.now()
    Position.objects.filter(account=account, status__in=[Position.Status.OPEN, Position.Status.PARTIAL]).update(
        status=Position.Status.CLOSED,
        closed_at=now,
        remaining_size=Decimal("0"),
    )

    account.balance = default_balance
    account.equity = default_balance
    account.save(update_fields=["balance", "equity"])

    return account
