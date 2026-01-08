from decimal import Decimal
import logging
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

from accounts.models import Account, Transaction
from common.enums import AccountType, TransactionType, TransactionStatus
from common.exceptions import SecurityException

if TYPE_CHECKING:
    from trading.models import Position

logger = logging.getLogger(__name__)


class PnLValidationService:
    @staticmethod
    @transaction.atomic
    def apply_trade_result(
        *,
        position: "Position",
        closing_price: Decimal,
        trade_account_type: str,
    ) -> Transaction:
        account: Account = position.account

        logger.info(
            "PnL apply requested",
            extra={
                "position_id": getattr(position, "id", None),
                "account_id": getattr(account, "id", None),
                "account_type": account.account_type,
                "trade_account_type": trade_account_type,
                "closing_price": str(closing_price),
            },
        )

        normalized_trade_type = (trade_account_type or "").lower()
        if normalized_trade_type not in {AccountType.DEMO.value, AccountType.REAL.value}:
            logger.error(
                "Unknown trade_account_type received for PnL",
                extra={
                    "trade_account_type": trade_account_type,
                    "position_id": getattr(position, "id", None),
                },
            )
            raise SecurityException(
                message="Unknown trade_account_type for PnL operation",
                details={"trade_account_type": trade_account_type},
            )

        if account.account_type != normalized_trade_type:
            logger.error(
                "PnL security isolation violation: account_type mismatch",
                extra={
                    "account_id": str(account.id),
                    "account_type": account.account_type,
                    "trade_account_type": normalized_trade_type,
                    "position_id": getattr(position, "id", None),
                },
            )
            raise SecurityException(
                message="Account type mismatch for PnL operation",
                details={
                    "account_id": str(account.id),
                    "account_type": account.account_type,
                    "trade_account_type": normalized_trade_type,
                },
            )
        entry_price: Decimal = position.entry_price
        qty: Decimal = position.position_size

        side = (getattr(position, "side", "") or "").upper()
        if side == "BUY":
            pnl = (closing_price - entry_price) * qty
        elif side == "SELL":
            pnl = (entry_price - closing_price) * qty
        else:
            logger.error(
                "Unknown position side when calculating PnL",
                extra={
                    "position_id": getattr(position, "id", None),
                    "side": position.side,
                },
            )
            raise ValueError("Unknown position side for PnL calculation")

        pnl = pnl.quantize(Decimal("0.01"))

        balance_before = account.balance
        balance_after = balance_before + pnl

        account.balance = balance_after
        account.equity = (account.equity or Decimal("0.00")) + pnl
        account.save(update_fields=["balance", "equity"])

        if hasattr(position, "pnl"):
            position.pnl = pnl
        if hasattr(position, "status"):
            position.status = getattr(position, "Status", None).CLOSED if hasattr(
                position, "Status"
            ) else "CLOSED"
        if hasattr(position, "closed_at"):
            position.closed_at = timezone.now()
        position.save()

        transaction_obj = Transaction.objects.create(
            account=account,
            transaction_type=TransactionType.TRADE_PNL.value,
            status=TransactionStatus.COMPLETED.value,
            amount=pnl,
            balance_before=balance_before,
            balance_after=balance_after,
            trade_id=getattr(position, "id", None),
            description="Trade PnL applied",
            metadata={
                "position_id": str(getattr(position, "id", "")),
                "entry_price": str(entry_price),
                "closing_price": str(closing_price),
                "position_size": str(qty),
                "side": side,
                "pnl": str(pnl),
                "normalized_trade_account_type": normalized_trade_type,
            },
        )

        logger.info(
            "PnL successfully applied",
            extra={
                "transaction_id": str(transaction_obj.id),
                "account_id": str(account.id),
                "pnl": str(pnl),
                "balance_before": str(balance_before),
                "balance_after": str(balance_after),
            },
        )

        return transaction_obj

