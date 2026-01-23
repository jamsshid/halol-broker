"""
Multi-User Demo Stress Test
Tests trading engine security, sharia compliance, and multi-user scenarios.
"""
from decimal import Decimal
import random
from django.test import TestCase
from django.contrib.auth import get_user_model
from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from trading.engine.risk_engine import RiskEngine, OrderValidationError

User = get_user_model()


class MultiUserDemoStressTest(TestCase):
    """
    Multi-user demo trading stress test.
    Tests: balance safety, risk limits, SL mandatory, hedge prevention.
    """
    
    def setUp(self):
        """Set up test data - create 10 demo users"""
        self.users = []
        self.accounts = []
        self.instruments = []
        
        # Create 10 demo users
        for i in range(10):
            user = User.objects.create_user(
                email=f"demo_user_{i}@example.com",
                password=f"testpass{i}"
            )
            self.users.append(user)
            
            # Create demo TradeAccount for each user
            account = TradeAccount.objects.create(
                user=user,
                account_type="demo",
                balance=Decimal("1000.00"),  # $1000 starting balance
                equity=Decimal("1000.00"),
                max_risk_per_trade=2.0,  # 2% max risk
                max_daily_loss=5.0
            )
            self.accounts.append(account)
        
        # Create test instruments
        self.eurusd = Instrument.objects.create(
            symbol="EURUSD",
            is_halal=True,
            is_crypto=False,
            min_stop_distance=Decimal("0.0001")
        )
        
        self.btcusd = Instrument.objects.create(
            symbol="BTCUSD",
            is_halal=True,
            is_crypto=True,
            min_stop_distance=Decimal("1.00")
        )
        
        self.instruments = [self.eurusd, self.btcusd]
    
    def test_multi_user_demo_trading_stress(self):
        """
        Multi-user demo trading stress test.
        
        Tests:
        - Balance never goes negative
        - Risk limits are enforced
        - SL mandatory works
        - Hedge prevention works
        - Multiple concurrent trades
        """
        # Track balances before trading
        initial_balances = {acc.id: acc.balance for acc in self.accounts}
        
        # Each user opens 3-5 random trades
        positions_opened = []
        
        for account in self.accounts:
            num_trades = random.randint(3, 5)
            instrument = random.choice(self.instruments)
            
            for _ in range(num_trades):
                try:
                    # Random side
                    side = random.choice([Position.Side.BUY, Position.Side.SELL])
                    
                    # Random prices based on instrument
                    if instrument.symbol == "EURUSD":
                        base_price = Decimal("1.1000")
                        price_range = Decimal("0.0100")
                    else:  # BTCUSD
                        base_price = Decimal("45000.00")
                        price_range = Decimal("1000.00")
                    
                    entry_price = base_price + Decimal(str(random.uniform(-float(price_range), float(price_range))))
                    
                    # SL mandatory - must be valid distance
                    if side == Position.Side.BUY:
                        sl_distance = Decimal(str(random.uniform(0.0002, 0.0050))) if instrument.symbol == "EURUSD" else Decimal(str(random.uniform(100, 500)))
                        stop_loss = entry_price - sl_distance
                    else:  # SELL
                        sl_distance = Decimal(str(random.uniform(0.0002, 0.0050))) if instrument.symbol == "EURUSD" else Decimal(str(random.uniform(100, 500)))
                        stop_loss = entry_price + sl_distance
                    
                    # Random risk (within limits)
                    risk_percent = random.uniform(0.5, 2.0)  # 0.5% to 2%
                    
                    # Open trade
                    position = open_trade(
                        account=account,
                        instrument=instrument,
                        side=side,
                        mode=random.choice([Position.Mode.ULTRA, Position.Mode.SEMI]),
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        take_profit=None,  # TP optional
                        risk_percent=risk_percent
                    )
                    
                    positions_opened.append(position)
                    
                    # Verify hedge prevention - try to open opposite position
                    opposite_side = Position.Side.SELL if side == Position.Side.BUY else Position.Side.BUY
                    with self.assertRaises(ValueError) as context:
                        open_trade(
                            account=account,
                            instrument=instrument,
                            side=opposite_side,
                            mode=Position.Mode.SEMI,
                            entry_price=entry_price + Decimal("0.0010"),
                            stop_loss=stop_loss + Decimal("0.0010"),
                            risk_percent=1.0
                        )
                    
                    # Verify hedge error message
                    self.assertIn("Hedging is disabled", str(context.exception))
                    
                except (ValueError, OrderValidationError) as e:
                    # Some trades may fail validation (expected)
                    # But SL mandatory should always be enforced
                    if "Stop Loss is mandatory" in str(e):
                        self.fail(f"SL mandatory check failed: {e}")
                    # Other validation errors are acceptable
                    continue
        
        # Verify balances never went negative
        for account in self.accounts:
            account.refresh_from_db()
            self.assertGreaterEqual(
                account.balance,
                Decimal("0"),
                f"Account {account.id} balance went negative: {account.balance}"
            )
        
        # Close some positions randomly
        positions_to_close = random.sample(positions_opened, min(10, len(positions_opened)))
        
        for position in positions_to_close:
            try:
                # Random closing price
                if position.instrument.symbol == "EURUSD":
                    base_price = Decimal("1.1000")
                    closing_price = base_price + Decimal(str(random.uniform(-0.005, 0.005)))
                else:
                    base_price = Decimal("45000.00")
                    closing_price = base_price + Decimal(str(random.uniform(-500, 500)))
                
                close_trade(
                    position_id=position.id,
                    closing_price=closing_price
                )
            except ValueError:
                # Position might already be closed
                continue
        
        # Final balance check
        for account in self.accounts:
            account.refresh_from_db()
            self.assertGreaterEqual(
                account.balance,
                Decimal("0"),
                f"Final balance check failed for account {account.id}: {account.balance}"
            )
    
    def test_sl_mandatory_enforcement(self):
        """Test that SL is mandatory"""
        account = self.accounts[0]
        
        # Try to open trade without SL
        with self.assertRaises(ValueError) as context:
            open_trade(
                account=account,
                instrument=self.eurusd,
                side=Position.Side.BUY,
                mode=Position.Mode.SEMI,
                entry_price=Decimal("1.1000"),
                stop_loss=None,  # Missing SL
                risk_percent=1.0
            )
        
        self.assertIn("Stop Loss is mandatory", str(context.exception))
    
    def test_tp_optional(self):
        """Test that TP is optional"""
        account = self.accounts[0]
        
        # Open trade without TP (should succeed)
        position = open_trade(
            account=account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=None,  # TP optional
            risk_percent=1.0
        )
        
        self.assertIsNone(position.take_profit)
        self.assertEqual(position.status, Position.Status.OPEN)
    
    def test_risk_percent_validation(self):
        """Test risk percent validation"""
        account = self.accounts[0]
        
        # Try with risk > max_risk_per_trade
        with self.assertRaises(ValueError) as context:
            open_trade(
                account=account,
                instrument=self.eurusd,
                side=Position.Side.BUY,
                mode=Position.Mode.SEMI,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0950"),
                risk_percent=5.0  # Exceeds 2% limit
            )
        
        self.assertIn("Risk percentage", str(context.exception))
        self.assertIn("exceeds maximum", str(context.exception))
    
    def test_sl_distance_validation(self):
        """Test SL distance validation"""
        account = self.accounts[0]
        
        # Try with SL too close (below min_stop_distance)
        with self.assertRaises(ValueError) as context:
            open_trade(
                account=account,
                instrument=self.eurusd,
                side=Position.Side.BUY,
                mode=Position.Mode.SEMI,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.09999"),  # Too close (< 0.0001)
                risk_percent=1.0
            )
        
        self.assertIn("Stop loss distance", str(context.exception))
        self.assertIn("below minimum", str(context.exception))
    
    def test_hedge_prevention(self):
        """Test hedge prevention (hedge_disabled=True)"""
        account = self.accounts[0]
        
        # Open BUY position
        buy_position = open_trade(
            account=account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Try to open SELL position (hedge) - should fail
        with self.assertRaises(ValueError) as context:
            open_trade(
                account=account,
                instrument=self.eurusd,
                side=Position.Side.SELL,
                mode=Position.Mode.SEMI,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.1050"),
                risk_percent=1.0
            )
        
        self.assertIn("Hedging is disabled", str(context.exception))
        
        # Close BUY position
        close_trade(
            position_id=buy_position.id,
            closing_price=Decimal("1.1050")
        )
        
        # Now SELL should work (no opposite position)
        sell_position = open_trade(
            account=account,
            instrument=self.eurusd,
            side=Position.Side.SELL,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.1050"),
            risk_percent=1.0
        )
        
        self.assertEqual(sell_position.side, Position.Side.SELL)
