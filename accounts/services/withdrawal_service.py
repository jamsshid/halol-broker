from django.db import transaction
from django.utils import timezone
from ..models import Account, Wallet, Transaction, Withdrawal
from common.enums import TransactionType, TransactionStatus
from common.constants import Fees
from common.exceptions import InsufficientBalanceError


class WithdrawalService:

    @staticmethod
    def calculate_withdrawal_fee(amount, payment_method):
        """Calculate withdrawal fee"""
        if payment_method.startswith("crypto"):
            return Fees.CRYPTO_WITHDRAW_FEE_FIXED

        fee = amount * (Fees.WITHDRAW_FEE_PERCENT / 100)
        return max(fee, Fees.WITHDRAW_FEE_MIN)

    @staticmethod
    @transaction.atomic
    def create_withdrawal(
        account_id,
        payment_method,
        amount,
        destination_address,
        destination_details=None,
    ):
        """Create withdrawal request"""
        account = Account.objects.select_for_update().get(id=account_id)

        fee = WithdrawalService.calculate_withdrawal_fee(amount, payment_method)
        total_amount = amount + fee

        if account.available_balance < total_amount:
            raise InsufficientBalanceError(
                f"Insufficient balance. Available: {account.available_balance}, Required: {total_amount}"
            )

        # Create transaction
        txn = Transaction.objects.create(
            account=account,
            transaction_type=TransactionType.WITHDRAW.value,
            status=TransactionStatus.PENDING.value,
            amount=-total_amount,
            balance_before=account.balance,
            balance_after=account.balance,  # Will update on completion
            description=f"Withdrawal via {payment_method}",
        )

        withdrawal = Withdrawal.objects.create(
            account=account,
            transaction=txn,
            payment_method=payment_method,
            amount=amount,
            fee=fee,
            net_amount=amount,
            destination_address=destination_address,
            destination_details=destination_details or {},
            status=TransactionStatus.PENDING.value,
        )

        return withdrawal

    @staticmethod
    @transaction.atomic
    def approve_withdrawal(withdrawal_id, approved_by_user_id):
        """Admin approves withdrawal"""
        withdrawal = Withdrawal.objects.select_for_update().get(id=withdrawal_id)

        if withdrawal.status != TransactionStatus.PENDING.value:
            raise ValueError(f"Withdrawal {withdrawal_id} is not pending")

        withdrawal.status = TransactionStatus.PROCESSING.value
        withdrawal.approved_by_id = approved_by_user_id
        withdrawal.approved_at = timezone.now()
        withdrawal.save()

        return withdrawal

    @staticmethod
    @transaction.atomic
    def complete_withdrawal(
        withdrawal_id, gateway_transaction_id="", gateway_response=None
    ):
        """Complete withdrawal and debit account"""
        withdrawal = Withdrawal.objects.select_for_update().get(id=withdrawal_id)
        account = Account.objects.select_for_update().get(id=withdrawal.account_id)
        wallet = Wallet.objects.select_for_update().get(account=account)

        total_amount = withdrawal.amount + withdrawal.fee

        # Update account balance
        account.balance -= total_amount
        account.save()

        # Update wallet stats
        wallet.total_withdrawals += withdrawal.amount
        wallet.total_fees_paid += withdrawal.fee
        wallet.save()

        # Update transaction
        withdrawal.transaction.status = TransactionStatus.COMPLETED.value
        withdrawal.transaction.balance_after = account.balance
        withdrawal.transaction.completed_at = timezone.now()
        withdrawal.transaction.save()

        # Update withdrawal
        withdrawal.status = TransactionStatus.COMPLETED.value
        withdrawal.gateway_transaction_id = gateway_transaction_id
        withdrawal.gateway_response = gateway_response or {}
        withdrawal.completed_at = timezone.now()
        withdrawal.save()

        return withdrawal

    @staticmethod
    @transaction.atomic
    def reject_withdrawal(withdrawal_id, rejection_reason, rejected_by_user_id):
        """Reject withdrawal request"""
        withdrawal = Withdrawal.objects.select_for_update().get(id=withdrawal_id)

        withdrawal.status = TransactionStatus.CANCELLED.value
        withdrawal.rejection_reason = rejection_reason
        withdrawal.approved_by_id = rejected_by_user_id
        withdrawal.approved_at = timezone.now()
        withdrawal.save()

        withdrawal.transaction.status = TransactionStatus.CANCELLED.value
        withdrawal.transaction.save()

        return withdrawal
