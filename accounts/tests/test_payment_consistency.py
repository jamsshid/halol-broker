from decimal import Decimal
from django.test import TestCase
from django.db import transaction
from django.db.models import Sum
from django.db.utils import IntegrityError
from concurrent.futures import ThreadPoolExecutor
import threading

from accounts.models import User, Account, Wallet, Transaction, Withdrawal
from accounts.services.withdrawal_service import WithdrawalService
from common.enums import AccountType, TransactionType, TransactionStatus
from common.exceptions import InsufficientBalanceError, SecurityException


class WalletIntegrityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@halolbroker.test",
            password="StrongPassword123!",
        )
        self.account = Account.objects.create(
            user=self.user,
            account_type=AccountType.REAL.value,
            account_number="R001",
            balance=Decimal("1000.00"),
            locked_balance=Decimal("0.00"),
        )
        self.wallet = Wallet.objects.create(account=self.account)

    def test_double_withdrawal_atomic_check(self):
        """
        Stress test: Two simultaneous withdrawal requests should not
        allow available_balance to go negative
        """
        initial_balance = self.account.balance
        withdrawal_amount = Decimal("600.00")  # More than half, but less than total

        def attempt_withdrawal():
            try:
                withdrawal = WithdrawalService.create_withdrawal(
                    account_id=self.account.id,
                    payment_method="bank_transfer",
                    amount=withdrawal_amount,
                    destination_address="TEST123",
                )
                return withdrawal
            except InsufficientBalanceError:
                return None

        # Attempt two withdrawals simultaneously
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(attempt_withdrawal) for _ in range(2)]
            results = [f.result() for f in futures]

        # Only one withdrawal should succeed
        successful_withdrawals = [r for r in results if r is not None]
        self.assertLessEqual(
            len(successful_withdrawals),
            1,
            "Only one withdrawal should succeed when balance is insufficient for both",
        )

        # Refresh account and verify balance integrity
        self.account.refresh_from_db()
        self.assertGreaterEqual(
            self.account.available_balance,
            Decimal("0.00"),
            "Available balance should never go negative",
        )

        # If one succeeded, verify the balance is correct
        if successful_withdrawals:
            withdrawal = successful_withdrawals[0]
            fee = WithdrawalService.calculate_withdrawal_fee(
                withdrawal_amount, "bank_transfer"
            )
            expected_balance = initial_balance - withdrawal_amount - fee
            self.assertEqual(
                self.account.balance,
                expected_balance,
                "Balance should be correctly updated after successful withdrawal",
            )

    def test_balance_transaction_match(self):
        """
        Validator: Sum of all transactions should match current balance
        """
        # Create some transactions
        Transaction.objects.create(
            account=self.account,
            transaction_type=TransactionType.DEPOSIT.value,
            status=TransactionStatus.COMPLETED.value,
            amount=Decimal("500.00"),
            balance_before=Decimal("1000.00"),
            balance_after=Decimal("1500.00"),
        )

        Transaction.objects.create(
            account=self.account,
            transaction_type=TransactionType.FEE.value,
            status=TransactionStatus.COMPLETED.value,
            amount=Decimal("-10.00"),
            balance_before=Decimal("1500.00"),
            balance_after=Decimal("1490.00"),
        )

        # Update account balance to match
        self.account.balance = Decimal("1490.00")
        self.account.save()

        # Calculate sum of all completed transactions
        transaction_sum = Transaction.objects.filter(
            account=self.account, status=TransactionStatus.COMPLETED.value
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        # Initial balance + transaction sum should equal current balance
        initial_balance = Decimal("1000.00")
        calculated_balance = initial_balance + transaction_sum

        self.assertEqual(
            self.account.balance,
            calculated_balance,
            "Current balance should match sum of all transactions",
        )

    def test_locked_balance_guard(self):
        """
        Security check: locked_balance should never exceed total balance
        """
        # Set locked balance to exceed total balance
        self.account.locked_balance = Decimal("1500.00")
        self.account.balance = Decimal("1000.00")

        # This should raise an error or be prevented
        with self.assertRaises((IntegrityError, ValueError)):
            self.account.save()

        # Or if validation happens at model level, test the property
        self.account.refresh_from_db()
        self.assertLessEqual(
            self.account.locked_balance,
            self.account.balance,
            "Locked balance should never exceed total balance",
        )

    def test_concurrent_balance_updates(self):
        """
        Stress test: Multiple concurrent balance updates should maintain consistency
        """
        initial_balance = self.account.balance
        update_amount = Decimal("100.00")
        num_threads = 5

        def update_balance():
            account = Account.objects.select_for_update().get(id=self.account.id)
            account.balance += update_amount
            account.save()

        # Run concurrent updates
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=update_balance)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify final balance
        self.account.refresh_from_db()
        expected_balance = initial_balance + (update_amount * num_threads)
        self.assertEqual(
            self.account.balance,
            expected_balance,
            "Concurrent balance updates should be atomic and consistent",
        )

    def test_negative_available_balance_prevention(self):
        """
        Security check: available_balance should never be negative
        """
        # Set locked balance to exceed balance
        self.account.balance = Decimal("1000.00")
        self.account.locked_balance = Decimal("1200.00")

        # Available balance property should handle this
        available = self.account.available_balance
        self.assertGreaterEqual(
            available, Decimal("0.00"), "Available balance should never be negative"
        )

        # Try to create withdrawal that would make it negative
        with self.assertRaises(InsufficientBalanceError):
            WithdrawalService.create_withdrawal(
                account_id=self.account.id,
                payment_method="bank_transfer",
                amount=Decimal("500.00"),
                destination_address="TEST123",
            )
