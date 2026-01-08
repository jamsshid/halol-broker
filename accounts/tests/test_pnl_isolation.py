from decimal import Decimal
import uuid
from unittest.mock import Mock

from django.test import TestCase

from accounts.models import User, Account, Transaction
from accounts.services.pnl_service import PnLValidationService
from common.enums import AccountType
from common.exceptions import SecurityException


class PnLIsolationTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="demo@halolbroker.test",
            password="StrongPassword123!",
        )

        # Real trading account
        self.real_account = Account.objects.create(
            user=self.user,
            account_type=AccountType.REAL.value,
            account_number="REAL-001",
            balance=Decimal("1000.00"),
            equity=Decimal("1000.00"),
        )

    def _create_mock_position(self):
        position = Mock()
        position.id = uuid.uuid4()
        position.account = self.real_account
        position.entry_price = Decimal("100.00")
        position.position_size = Decimal("1.00")
        position.side = "BUY"
        position.pnl = None
        position.status = "OPEN"
        position.closed_at = None
        position.save = Mock()  
        return position

    def test_demo_trade_cannot_apply_pnl_to_real_account(self):

        position = self._create_mock_position()

        initial_balance = self.real_account.balance
        initial_tx_count = Transaction.objects.filter(account=self.real_account).count()

        with self.assertRaises(SecurityException):
            PnLValidationService.apply_trade_result(
                position=position,
                closing_price=Decimal("105.00"),
                trade_account_type=AccountType.DEMO.value, 
            )


        self.real_account.refresh_from_db()
        self.assertEqual(self.real_account.balance, initial_balance)
        final_tx_count = Transaction.objects.filter(account=self.real_account).count()
        self.assertEqual(final_tx_count, initial_tx_count)

