from decimal import Decimal
from django.test import TestCase

from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from trading.services.demo import reset_demo_account, DEFAULT_DEMO_BALANCE


class DemoLifecycleTests(TestCase):
    def setUp(self):
        self.demo_account = TradeAccount.objects.create(
            user=None,
            account_type="demo",
            balance=Decimal("5000.00"),
            equity=Decimal("5000.00"),
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
        )
        self.instrument = Instrument.objects.create(
            symbol="BTCUSD",
            is_halal=True,
            is_crypto=True,
            min_stop_distance=Decimal("0.50"),
        )

    def test_demo_trade_open_close(self):
        position = open_trade(
            account=self.demo_account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode="SEMI",
            entry_price=Decimal("45000"),
            stop_loss=Decimal("44000"),
            take_profit=Decimal("47000"),
            risk_percent=Decimal("1.0"),
            timeframe="H1",
        )
        self.assertEqual(position.status, Position.Status.OPEN)

        closed = close_trade(
            position_id=position.id,
            closing_price=Decimal("46000"),
        )
        self.assertEqual(closed.status, Position.Status.CLOSED)
        # Demo account balance should not be changed by wallet sync (we skip backend-2)
        self.demo_account.refresh_from_db()
        self.assertEqual(self.demo_account.balance, Decimal("5000.00"))

    def test_demo_reset(self):
        # Open a trade to create state
        position = open_trade(
            account=self.demo_account,
            instrument=self.instrument,
            side=Position.Side.SELL,
            mode="ULTRA",
            entry_price=Decimal("45000"),
            stop_loss=Decimal("45500"),
            risk_percent=Decimal("1.0"),
        )
        self.assertEqual(position.status, Position.Status.OPEN)

        # Reset demo
        reset_demo_account(self.demo_account)
        self.demo_account.refresh_from_db()
        self.assertEqual(self.demo_account.balance, DEFAULT_DEMO_BALANCE)
        self.assertEqual(self.demo_account.equity, DEFAULT_DEMO_BALANCE)

        position.refresh_from_db()
        self.assertEqual(position.status, Position.Status.CLOSED)
        self.assertEqual(position.remaining_size, Decimal("0"))
