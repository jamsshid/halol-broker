from decimal import Decimal
from django.test import TestCase

from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.risk_limits import RiskGuard, MockLimitServiceClient
from common.exceptions import RiskLimitError


class RiskEnforcementTests(TestCase):
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
            symbol="ETHUSD",
            is_halal=True,
            is_crypto=True,
            min_stop_distance=Decimal("1.00"),
        )

    def test_risk_percent_exceeded(self):
        with self.assertRaises(RiskLimitError):
            open_trade(
                account=self.account,
                instrument=self.instrument,
                side=Position.Side.BUY,
                mode="SEMI",
                entry_price=Decimal("2000"),
                stop_loss=Decimal("1900"),
                risk_percent=Decimal("3.5"),  # exceeds 2%
            )

    def test_daily_loss_exceeded(self):
        # Inject custom daily loss via mock client
        limit_client = MockLimitServiceClient()
        limit_client.set_daily_loss(self.account.id, Decimal("600"))  # 6% of 10k
        guard = RiskGuard(limit_client=limit_client)

        with self.assertRaises(RiskLimitError):
            guard.enforce(account=self.account, risk_percent=Decimal("1.0"), mode="ULTRA")

    def test_mode_changes_allowed(self):
        # Mode-specific risk handled in mode policy; guard should pass for valid numbers
        limit_client = MockLimitServiceClient()
        guard = RiskGuard(limit_client=limit_client)
        self.assertTrue(guard.enforce(account=self.account, risk_percent=Decimal("1.0"), mode="ULTRA"))
        self.assertTrue(guard.enforce(account=self.account, risk_percent=Decimal("1.8"), mode="SEMI"))
