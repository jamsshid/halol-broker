from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum
import logging
import time
from typing import Optional, Dict, Any
from ..models import Account, Wallet, Transaction
from common.enums import TransactionType, TransactionStatus
from common.exceptions import InsufficientBalanceError, AccountSuspendedError, PaymentGatewayError


class WalletService:
    """Core wallet operations"""

    @staticmethod
    @transaction.atomic
    def lock_balance(account_id, amount, trade_id, description=""):
        """
        Lock balance for trade margin.
        
        Uses select_for_update(skip_locked=True) to prevent deadlocks
        in multi-user scenarios.
        """
        # Use skip_locked=True to prevent deadlocks when multiple users
        # try to lock balance simultaneously
        account = Account.objects.select_for_update(skip_locked=True).get(id=account_id)

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

        # Check for risk alerts after applying loss
        if pnl_amount < 0:
            from .alert_service import AlertService
            AlertService.check_and_create_risk_alert(account_id)

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

    @staticmethod
    def audit_balance(account_id, initial_balance=None):
        """
        Data Consistency Audit: Verify that account balance matches
        the sum of all completed transactions.

        Args:
            account_id: UUID of the account to audit
            initial_balance: Optional initial balance at account creation.
                           If not provided, assumes 0.00

        Returns:
            dict with audit results:
            {
                'is_consistent': bool,
                'account_balance': Decimal,
                'calculated_balance': Decimal,
                'transaction_sum': Decimal,
                'difference': Decimal,
                'transaction_count': int
            }
        """
        try:
            account = Account.objects.get(id=account_id)
        except Account.DoesNotExist:
            return {
                'is_consistent': False,
                'error': f'Account {account_id} not found'
            }

        # Get initial balance (default to 0.00 if not provided)
        if initial_balance is None:
            initial_balance = Decimal("0.00")

        # Calculate sum of all completed transactions
        completed_transactions = Transaction.objects.filter(
            account=account,
            status=TransactionStatus.COMPLETED.value
        )

        transaction_sum = completed_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal("0.00")

        # Calculate expected balance: initial_balance + sum of all transactions
        calculated_balance = initial_balance + transaction_sum

        # Get current account balance
        account_balance = account.balance

        # Calculate difference
        difference = account_balance - calculated_balance

        # Check consistency (allow for rounding differences up to 0.01)
        is_consistent = abs(difference) <= Decimal("0.01")

        return {
            'is_consistent': is_consistent,
            'account_balance': account_balance,
            'calculated_balance': calculated_balance,
            'transaction_sum': transaction_sum,
            'initial_balance': initial_balance,
            'difference': difference,
            'transaction_count': completed_transactions.count(),
            'account_id': str(account_id),
            'account_number': account.account_number,
        }

    @staticmethod
    @transaction.atomic
    def simulate_payment_flow(
        account_id,
        amount: Decimal,
        payment_method: str,
        gateway_timeout: int = 30,
        simulate_network_error: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Simulate payment flow with fail-safe rollback mechanism.
        
        This method simulates a payment gateway interaction with automatic
        rollback if network timeout occurs.
        
        Args:
            account_id: Account UUID
            amount: Payment amount
            payment_method: Payment method identifier
            gateway_timeout: Timeout in seconds (default: 30)
            simulate_network_error: If True, simulate network timeout for testing
            **kwargs: Additional parameters (gateway_url, etc.)
        
        Returns:
            Dict with payment result:
            {
                'success': bool,
                'transaction_id': str,
                'status': str,
                'message': str
            }
        
        Raises:
            PaymentGatewayError: If payment fails and rollback succeeds
            InsufficientBalanceError: If account has insufficient balance
            AccountSuspendedError: If account is suspended
        """
        logger = logging.getLogger(__name__)
        
        try:
            account = Account.objects.select_for_update().get(id=account_id)
            
            # Validate account status
            if account.status != "active":
                raise AccountSuspendedError(
                    f"Account {account.account_number} is {account.status}"
                )
            
            # Create pending transaction
            balance_before = account.balance
            txn = Transaction.objects.create(
                account=account,
                transaction_type=TransactionType.DEPOSIT.value,
                status=TransactionStatus.PROCESSING.value,
                amount=amount,
                balance_before=balance_before,
                balance_after=balance_before,  # Will update on completion
                payment_id=kwargs.get('payment_id', ''),
                description=f"Payment simulation via {payment_method}",
                metadata={
                    'payment_method': payment_method,
                    'gateway_timeout': gateway_timeout,
                    **kwargs
                }
            )
            
            logger.info(
                f"Payment simulation started: transaction_id={txn.id}, account_id={account_id}, amount={amount}"
            )
            
            # Simulate gateway call with timeout protection
            try:
                # Simulate network delay
                if simulate_network_error:
                    raise TimeoutError("Simulated network timeout")
                
                # In real implementation, this would be an actual gateway call
                # For simulation, we just wait a bit
                time.sleep(0.1)  # Simulate processing time
                
                # Simulate gateway response
                gateway_success = not simulate_network_error
                
                if not gateway_success:
                    raise TimeoutError("Payment gateway timeout")
                
                # Payment successful - update account balance
                account.balance += amount
                account.save()
                
                # Update wallet stats
                wallet, _ = Wallet.objects.get_or_create(account=account)
                wallet.total_deposits += amount
                wallet.save()
                
                # Complete transaction
                txn.status = TransactionStatus.COMPLETED.value
                txn.balance_after = account.balance
                txn.completed_at = timezone.now()
                txn.save()
                
                logger.info(
                    f"Payment simulation completed: transaction_id={txn.id}, new_balance={account.balance}"
                )
                
                return {
                    'success': True,
                    'transaction_id': str(txn.id),
                    'status': 'completed',
                    'message': 'Payment processed successfully',
                    'new_balance': str(account.balance)
                }
                
            except (TimeoutError, ConnectionError, Exception) as e:
                # Network timeout or gateway error - rollback transaction
                logger.warning(
                    f"Payment gateway error for transaction {txn.id}: {str(e)}. Initiating rollback."
                )
                
                # Rollback: Cancel transaction
                txn.status = TransactionStatus.FAILED.value
                txn.description = f"Payment failed: {str(e)}. Rolled back."
                txn.save()
                
                # Account balance was never updated, so no need to rollback balance
                # Transaction is marked as failed, which is sufficient
                
                raise PaymentGatewayError(
                    message=f"Payment gateway error: {str(e)}",
                    details={
                        'transaction_id': str(txn.id),
                        'account_id': str(account_id),
                        'amount': str(amount),
                        'rollback_status': 'completed',
                        'error_type': type(e).__name__
                    }
                )
                
        except (InsufficientBalanceError, AccountSuspendedError, PaymentGatewayError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in payment simulation: {str(e)}",
                exc_info=True
            )
            raise PaymentGatewayError(
                message=f"Unexpected payment error: {str(e)}",
                details={'error_type': type(e).__name__}
            )

    @staticmethod
    @transaction.atomic
    def simulate_withdrawal_flow(
        account_id,
        amount: Decimal,
        payment_method: str,
        destination_address: str,
        simulate_network_error: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Simulate withdrawal flow with fail-safe rollback mechanism.
        
        Withdraw QA: When withdrawing, if available_balance is sufficient,
        transfer to locked_balance and set status to 'PENDING_APPROVAL'.
        
        Args:
            account_id: Account UUID
            amount: Withdrawal amount
            payment_method: Payment method identifier
            destination_address: Destination address for withdrawal
            simulate_network_error: If True, simulate network timeout for testing
            **kwargs: Additional parameters
        
        Returns:
            Dict with withdrawal result
        
        Raises:
            InsufficientBalanceError: If available balance is insufficient
            AccountSuspendedError: If account is suspended
            PaymentGatewayError: If withdrawal fails and rollback succeeds
        """
        logger = logging.getLogger(__name__)
        
        try:
            account = Account.objects.select_for_update().get(id=account_id)
            
            # Validate account status
            if account.status != "active":
                raise AccountSuspendedError(
                    f"Account {account.account_number} is {account.status}"
                )
            
            # Check available balance
            if account.available_balance < amount:
                raise InsufficientBalanceError(
                    f"Insufficient available balance. Available: {account.available_balance}, Required: {amount}"
                )
            
            balance_before = account.balance
            locked_before = account.locked_balance
            
            # Create withdrawal transaction with PENDING_APPROVAL status
            txn = Transaction.objects.create(
                account=account,
                transaction_type=TransactionType.WITHDRAW.value,
                status=TransactionStatus.PENDING.value,  # PENDING_APPROVAL equivalent
                amount=-amount,
                balance_before=balance_before,
                balance_after=balance_before,  # Will update on approval/completion
                description=f"Withdrawal request via {payment_method} to {destination_address}",
                metadata={
                    'payment_method': payment_method,
                    'destination_address': destination_address,
                    **kwargs
                }
            )
            
            # Transfer from available_balance to locked_balance
            # This locks the funds until admin approval
            account.locked_balance += amount
            account.save()
            
            logger.info(
                f"Withdrawal simulation started: transaction_id={txn.id}, "
                f"account_id={account_id}, amount={amount}, "
                f"locked_balance={account.locked_balance}"
            )
            
            # Simulate gateway call (for testing)
            try:
                if simulate_network_error:
                    raise TimeoutError("Simulated network timeout")
                
                # In real implementation, this would notify admin for approval
                # For simulation, we just mark as pending
                time.sleep(0.1)  # Simulate processing time
                
                # Withdrawal request created successfully
                # Status remains PENDING until admin approval
                
                return {
                    'success': True,
                    'transaction_id': str(txn.id),
                    'status': 'pending_approval',
                    'message': 'Withdrawal request created. Awaiting admin approval.',
                    'locked_balance': str(account.locked_balance),
                    'available_balance': str(account.available_balance),
                    'note': 'Funds are locked until admin approval'
                }
                
            except (TimeoutError, ConnectionError, Exception) as e:
                # Network timeout or gateway error - rollback
                logger.warning(
                    f"Withdrawal gateway error for transaction {txn.id}: {str(e)}. Initiating rollback."
                )
                
                # Rollback: Release locked balance
                account.locked_balance -= amount
                if account.locked_balance < 0:
                    account.locked_balance = Decimal("0.00")
                account.save()
                
                # Mark transaction as failed
                txn.status = TransactionStatus.FAILED.value
                txn.description = f"Withdrawal failed: {str(e)}. Rolled back."
                txn.save()
                
                raise PaymentGatewayError(
                    message=f"Withdrawal gateway error: {str(e)}",
                    details={
                        'transaction_id': str(txn.id),
                        'account_id': str(account_id),
                        'amount': str(amount),
                        'rollback_status': 'completed',
                        'locked_balance_restored': True,
                        'error_type': type(e).__name__
                    }
                )
                
        except (InsufficientBalanceError, AccountSuspendedError, PaymentGatewayError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in withdrawal simulation: {str(e)}",
                exc_info=True
            )
            raise PaymentGatewayError(
                message=f"Unexpected withdrawal error: {str(e)}",
                details={'error_type': type(e).__name__}
            )
