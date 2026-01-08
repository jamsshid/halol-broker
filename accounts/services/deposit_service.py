from django.db import transaction
from django.utils import timezone
from ..models import Account, Wallet, Transaction, Deposit
from common.enums import TransactionType, TransactionStatus
import uuid


class DepositService:

    @staticmethod
    @transaction.atomic
    def create_deposit(account_id, payment_method, amount, currency="USD", **kwargs):
        """Create deposit request"""
        account = Account.objects.select_for_update().get(id=account_id)

        # Create transaction first
        txn = Transaction.objects.create(
            account=account,
            transaction_type=TransactionType.DEPOSIT.value,
            status=TransactionStatus.PENDING.value,
            amount=amount,
            balance_before=account.balance,
            balance_after=account.balance,  # Will 
            description=f"Deposit via {payment_method}",
        )

        deposit = Deposit.objects.create(
            account=account,
            transaction=txn,
            payment_method=payment_method,
            amount=amount,
            currency=currency,
            crypto_address=kwargs.get("crypto_address", ""),
            status=TransactionStatus.PENDING.value,
        )

        return deposit

    @staticmethod
    @transaction.atomic
    def complete_deposit(deposit_id, gateway_transaction_id="", gateway_response=None):
        """Complete deposit and credit account"""
        deposit = Deposit.objects.select_for_update().get(id=deposit_id)
        account = Account.objects.select_for_update().get(id=deposit.account_id)
        wallet = Wallet.objects.select_for_update().get(account=account)

        # Update account balance
        balance_before = account.balance
        account.balance += deposit.amount
        account.save()

        # Update wallet stats
        wallet.total_deposits += deposit.amount
        wallet.save()

        # Update transaction
        deposit.transaction.status = TransactionStatus.COMPLETED.value
        deposit.transaction.balance_after = account.balance
        deposit.transaction.completed_at = timezone.now()
        deposit.transaction.save()

        # Update deposit
        deposit.status = TransactionStatus.COMPLETED.value
        deposit.gateway_transaction_id = gateway_transaction_id
        deposit.gateway_response = gateway_response or {}
        deposit.completed_at = timezone.now()
        deposit.save()

        return deposit
