from decimal import Decimal
from django.test import TestCase

from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from trading.services.pnl_sync import MismatchBackend2Client, MockBackend2Client
from common.exceptions import TradeValidationError


class PnLSyncTests(TestCase):
    def setUp(self):
        self.account = TradeAccount.objects.create(
            user=None,
            account_type="real",
            balance=Decimal("10000.00"),
            equity=Decimal("10000.00"),
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
        )
        self.instrument = Instrument.objects.create(
            symbol="EURUSD",
            is_halal=True,
            is_crypto=False,
            min_stop_distance=Decimal("0.0001"),
        )

    def test_pnl_sync_success(self):
        position = open_trade(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode="ULTRA",
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0980"),
            take_profit=Decimal("1.1200"),
            risk_percent=Decimal("1.0"),
            timeframe="M1",
        )

        mock_client = MockBackend2Client()
        closed = close_trade(
            position_id=position.id,
            closing_price=Decimal("1.1050"),
            backend_client=mock_client,
        )

        self.assertEqual(closed.status, Position.Status.CLOSED)
        self.assertEqual(len(mock_client.calls), 1)
        self.assertIn("pnl", mock_client.calls[0])

    def test_pnl_mismatch_rollback(self):
        position = open_trade(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode="ULTRA",
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0980"),
            risk_percent=Decimal("1.0"),
            timeframe="M1",
        )

        with self.assertRaises(TradeValidationError):
            close_trade(
                position_id=position.id,
                closing_price=Decimal("1.1050"),
                backend_client=MismatchBackend2Client(delta=Decimal("1.00")),
            )

        # Position should remain OPEN because transaction rolled back
        position.refresh_from_db()
        self.assertEqual(position.status, Position.Status.OPEN)
