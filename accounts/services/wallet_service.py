from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from ..models import Account, Wallet, Transaction
from common.enums import TransactionType, TransactionStatus
from common.exceptions import InsufficientBalanceError, AccountSuspendedError


class WalletService:
    """Core wallet operations"""

    @staticmethod
    @transaction.atomic
    def lock_balance(account_id, amount, trade_id, description=""):
        """Lock balance for trade margin"""
        account = Account.objects.select_for_update().get(id=account_id)

        if account.status != "active":
            raise AccountSuspendedError(
                f"Account {account.account_number} is {account.status}"
            )

        if account.available_balance < amount:
            raise InsufficientBalanceError(
                f"Insufficient balance. Available: {account.available_balance}, Required: {amount}"
            )

        balance_before = account.balance
        account.locked_balance += amount
        account.save()

        txn = Transaction.objects.create(
            account=account,
            transaction_type=TransactionType.TRADE_LOCK.value,
            status=TransactionStatus.COMPLETED.value,
            amount=-amount,
            balance_before=balance_before,
            balance_after=account.balance,
            trade_id=trade_id,
            description=description or f"Margin locked for trade {trade_id}",
            completed_at=timezone.now(),
        )

        return txn

    @staticmethod
    @transaction.atomic
    def release_balance(account_id, amount, trade_id, description=""):
        """Release locked balance"""
        account = Account.objects.select_for_update().get(id=account_id)

        balance_before = account.balance
        account.locked_balance -= amount
        if account.locked_balance < 0:
            account.locked_balance = Decimal("0.00")
        account.save()

        txn = Transaction.objects.create(
            account=account,
            transaction_type=TransactionType.TRADE_RELEASE.value,
            status=TransactionStatus.COMPLETED.value,
            amount=amount,
            balance_before=balance_before,
            balance_after=account.balance,
            trade_id=trade_id,
            description=description or f"Margin released from trade {trade_id}",
            completed_at=timezone.now(),
        )

        return txn

    @staticmethod
    @transaction.atomic
    def apply_pnl(account_id, pnl_amount, trade_id, description=""):
        """Apply profit/loss to account"""
        account = Account.objects.select_for_update().get(id=account_id)
        wallet = Wallet.objects.select_for_update().get(account=account)

        balance_before = account.balance
        account.balance += pnl_amount

        if pnl_amount < 0:
            account.daily_loss_current += abs(pnl_amount)
            wallet.total_loss += abs(pnl_amount)
        else:
            wallet.total_profit += pnl_amount

        account.save()
        wallet.save()

        txn = Transaction.objects.create(
            account=account,
            transaction_type=TransactionType.TRADE_PNL.value,
            status=TransactionStatus.COMPLETED.value,
            amount=pnl_amount,
            balance_before=balance_before,
            balance_after=account.balance,
            trade_id=trade_id,
            description=description or f"PnL from trade {trade_id}",
            completed_at=timezone.now(),
        )

        return txn

    @staticmethod
    def check_daily_loss_limit(account):
        """Check if account exceeded daily loss limit"""
        if not account.max_daily_loss:
            return True

        # Reset daily loss if new day
        from datetime import date

        if account.daily_loss_reset_date < date.today():
            account.daily_loss_current = Decimal("0.00")
            account.daily_loss_reset_date = date.today()
            account.save()

        return account.daily_loss_current < account.max_daily_loss

    @staticmethod
    def calculate_margin_requirement(volume, leverage, price):
        """Calculate margin needed for position"""
        return (volume * price) / leverage
