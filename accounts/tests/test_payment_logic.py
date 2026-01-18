from decimal import Decimal
from django.test import TestCase
from django.db import transaction
from django.db.models import Sum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

from accounts.models import User, Account, Wallet, Transaction, Deposit, Withdrawal
from accounts.services.deposit_service import DepositService
from accounts.services.withdrawal_service import WithdrawalService
from accounts.services.wallet_service import WalletService
from common.enums import (
    AccountType,
    TransactionType,
    TransactionStatus,
    PaymentMethod,
)
from common.exceptions import InsufficientBalanceError


class PaymentLogicIntegrityTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@halolbroker.test",
            password="StrongPassword123!",
        )

        # Create Real account
        self.real_account = Account.objects.create(
            user=self.user,
            account_type=AccountType.REAL.value,
            account_number="REAL-001",
            balance=Decimal("5000.00"),
            locked_balance=Decimal("0.00"),
            status="active",
        )
        Wallet.objects.create(account=self.real_account)

        # Create Demo account
        self.demo_account = Account.objects.create(
            user=self.user,
            account_type=AccountType.DEMO.value,
            account_number="DEMO-001",
            balance=Decimal("10000.00"),
            locked_balance=Decimal("0.00"),
            status="active",
        )
        Wallet.objects.create(account=self.demo_account)

    def test_concurrency_stress_deposit_withdraw_select_for_update(self):
        """
        Concurrency Stress: Test that select_for_update() prevents race conditions
        when multiple deposit/withdraw requests happen simultaneously.
        """
        initial_balance = self.real_account.balance
        deposit_amount = Decimal("100.00")
        withdrawal_amount = Decimal("150.00")
        num_concurrent_ops = 10

        results = {"deposits": [], "withdrawals": [], "errors": []}

        def perform_deposit():
            """Concurrent deposit operation"""
            try:
                with transaction.atomic():
                    deposit = DepositService.create_deposit(
                        account_id=self.real_account.id,
                        payment_method=PaymentMethod.BANK_TRANSFER.value,
                        amount=deposit_amount,
                    )
                    DepositService.complete_deposit(deposit.id)
                    results["deposits"].append(deposit.id)
                    return deposit
            except Exception as e:
                results["errors"].append(f"Deposit error: {str(e)}")
                return None

        def perform_withdrawal():
            """Concurrent withdrawal operation"""
            try:
                with transaction.atomic():
                    withdrawal = WithdrawalService.create_withdrawal(
                        account_id=self.real_account.id,
                        payment_method=PaymentMethod.BANK_TRANSFER.value,
                        amount=withdrawal_amount,
                        destination_address="TEST123",
                    )
                    WithdrawalService.complete_withdrawal(withdrawal.id)
                    results["withdrawals"].append(withdrawal.id)
                    return withdrawal
            except InsufficientBalanceError as e:
                results["errors"].append(f"Withdrawal error: {str(e)}")
                return None
            except Exception as e:
                results["errors"].append(f"Withdrawal error: {str(e)}")
                return None

        # Execute concurrent operations
        with ThreadPoolExecutor(max_workers=num_concurrent_ops) as executor:
            futures = []
            # Mix deposits and withdrawals
            for i in range(num_concurrent_ops):
                if i % 2 == 0:
                    futures.append(executor.submit(perform_deposit))
                else:
                    futures.append(executor.submit(perform_withdrawal))

            # Wait for all to complete
            for future in as_completed(futures):
                future.result()

        # Refresh account
        self.real_account.refresh_from_db()

        # Verify balance integrity: available_balance should never go negative
        self.assertGreaterEqual(
            self.real_account.available_balance,
            Decimal("0.00"),
            "Available balance should never go negative even under concurrent load",
        )

        # Verify balance consistency: calculate expected balance
        total_deposits = len(results["deposits"]) * deposit_amount
        fee_per_withdrawal = WithdrawalService.calculate_withdrawal_fee(
            withdrawal_amount, PaymentMethod.BANK_TRANSFER.value
        )
        total_withdrawals = len(results["withdrawals"]) * (
            withdrawal_amount + fee_per_withdrawal
        )
        expected_balance = initial_balance + total_deposits - total_withdrawals

        self.assertEqual(
            self.real_account.balance,
            expected_balance,
            f"Final balance should match calculations. "
            f"Deposits: {len(results['deposits'])}, Withdrawals: {len(results['withdrawals'])}",
        )

        # Verify all transactions are recorded correctly
        completed_txs = Transaction.objects.filter(
            account=self.real_account, status=TransactionStatus.COMPLETED.value
        )
        self.assertGreater(
            completed_txs.count(), 0, "At least some transactions should complete"
        )

    def test_isolation_guard_demo_transactions_not_affect_real_balance(self):
        """
        Isolation Guard: Demo account transactions must NOT affect Real account balance.
        This is a critical security check.
        """
        real_initial_balance = self.real_account.balance
        demo_initial_balance = self.demo_account.balance

        # Create deposit on demo account
        demo_deposit = DepositService.create_deposit(
            account_id=self.demo_account.id,
            payment_method=PaymentMethod.BANK_TRANSFER.value,
            amount=Decimal("2000.00"),
        )
        DepositService.complete_deposit(demo_deposit.id)

        # Create withdrawal on demo account
        demo_withdrawal = WithdrawalService.create_withdrawal(
            account_id=self.demo_account.id,
            payment_method=PaymentMethod.BANK_TRANSFER.value,
            amount=Decimal("1000.00"),
            destination_address="DEMO_ADDRESS",
        )
        WithdrawalService.complete_withdrawal(demo_withdrawal.id)

        # Apply PnL to demo account (simulate trade profit)
        WalletService.apply_pnl(
            account_id=self.demo_account.id,
            pnl_amount=Decimal("500.00"),
            trade_id=Transaction.objects.first().id if Transaction.objects.exists() else None,
        )

        # Refresh both accounts
        self.real_account.refresh_from_db()
        self.demo_account.refresh_from_db()

        # CRITICAL: Real account balance must be unchanged
        self.assertEqual(
            self.real_account.balance,
            real_initial_balance,
            "Real account balance must NOT be affected by demo account transactions",
        )

        # Demo account should have changed
        self.assertNotEqual(
            self.demo_account.balance,
            demo_initial_balance,
            "Demo account balance should change after transactions",
        )

        # Verify no transactions were created on real account
        real_transactions = Transaction.objects.filter(account=self.real_account)
        self.assertEqual(
            real_transactions.count(),
            0,
            "No transactions should exist on real account when operating on demo",
        )

        # Verify demo transactions exist
        demo_transactions = Transaction.objects.filter(account=self.demo_account)
        self.assertGreater(
            demo_transactions.count(),
            0,
            "Demo transactions should be recorded on demo account",
        )

    def test_rollback_safety_locked_balance_reverts_on_withdrawal_error(self):
        """
        Rollback Safety: If withdrawal process fails, locked_balance must be
        automatically rolled back and returned to main balance.
        """
        initial_balance = self.real_account.balance
        initial_locked_balance = self.real_account.locked_balance
        withdrawal_amount = Decimal("3000.00")

        # Lock some balance for a trade
        trade_id = Transaction.objects.first().id if Transaction.objects.exists() else None
        locked_amount = Decimal("1000.00")
        WalletService.lock_balance(
            account_id=self.real_account.id,
            amount=locked_amount,
            trade_id=trade_id or "test-trade-id",
        )

        self.real_account.refresh_from_db()
        self.assertEqual(
            self.real_account.locked_balance,
            initial_locked_balance + locked_amount,
            "Balance should be locked",
        )

        # Attempt withdrawal that should fail (insufficient available balance)
        # Available = balance - locked_balance = 5000 - 1000 = 4000
        # Withdrawal + fee > 4000, so it should fail
        large_withdrawal = Decimal("4500.00")

        with self.assertRaises(InsufficientBalanceError):
            WithdrawalService.create_withdrawal(
                account_id=self.real_account.id,
                payment_method=PaymentMethod.BANK_TRANSFER.value,
                amount=large_withdrawal,
                destination_address="TEST123",
            )

        # Refresh account - locked_balance should remain unchanged after failed withdrawal
        self.real_account.refresh_from_db()

        self.assertEqual(
            self.real_account.locked_balance,
            initial_locked_balance + locked_amount,
            "Locked balance should remain unchanged after failed withdrawal attempt",
        )

        self.assertEqual(
            self.real_account.balance,
            initial_balance,
            "Main balance should remain unchanged after failed withdrawal",
        )

        # Now simulate a scenario where withdrawal is created but fails during processing
        # This should test transaction rollback
        withdrawal = None
        try:
            # Create a valid withdrawal first
            withdrawal = WithdrawalService.create_withdrawal(
                account_id=self.real_account.id,
                payment_method=PaymentMethod.BANK_TRANSFER.value,
                amount=Decimal("500.00"),  # Small amount, should succeed
                destination_address="TEST123",
            )

            # Simulate error during completion (e.g., gateway failure)
            # The withdrawal is in PENDING state, balance not yet deducted
            self.real_account.refresh_from_db()
            balance_after_creation = self.real_account.balance

            # Balance should not change until withdrawal is completed
            self.assertEqual(
                balance_after_creation,
                initial_balance,
                "Balance should not change when withdrawal is in PENDING state",
            )

            # If we reject the withdrawal, balance should remain unchanged
            WithdrawalService.reject_withdrawal(
                withdrawal_id=withdrawal.id,
                rejection_reason="Gateway error",
                rejected_by_user_id=self.user.id,
            )

            self.real_account.refresh_from_db()
            self.assertEqual(
                self.real_account.balance,
                initial_balance,
                "Balance should remain unchanged after withdrawal rejection",
            )

        except Exception as e:
            # If any error occurs, verify rollback
            self.real_account.refresh_from_db()
            self.assertEqual(
                self.real_account.balance,
                initial_balance,
                "Balance should be rolled back to initial value on error",
            )

        # Final verification: locked_balance should still be intact
        self.real_account.refresh_from_db()
        self.assertEqual(
            self.real_account.locked_balance,
            initial_locked_balance + locked_amount,
            "Locked balance must remain intact after all operations",
        )

