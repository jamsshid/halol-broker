"""
Trade Engine Edge Cases Tests
Tests: SL hit, TP hit, Partial close, Gap/spike, $1 balance
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from trading.engine.pnl_engine import PnLEngine
from market.price_feed import get_price_feed

User = get_user_model()


class TradeEngineEdgeCasesTest(TestCase):
    """Test edge cases for trade engine"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        
        # Demo account with $1 balance (edge case)
        self.demo_account = TradeAccount.objects.create(
            user=self.user,
            account_type="demo",
            balance=Decimal("1.00"),
            equity=Decimal("1.00"),
            max_risk_per_trade=2.0,
            max_daily_loss=5.0
        )
        
        # Real account
        self.real_account = TradeAccount.objects.create(
            user=self.user,
            account_type="real",
            balance=Decimal("1000.00"),
            equity=Decimal("1000.00"),
            max_risk_per_trade=2.0,
            max_daily_loss=5.0
        )
        
        # Forex instrument
        self.eurusd = Instrument.objects.create(
            symbol="EURUSD",
            is_halal=True,
            is_crypto=False,
            min_stop_distance=Decimal("0.0001")
        )
        
        # Crypto instrument (halal)
        self.btcusd = Instrument.objects.create(
            symbol="BTCUSD",
            is_halal=True,
            is_crypto=True,
            min_stop_distance=Decimal("1.00")
        )
    
    def test_sl_hit_buy(self):
        """Test stop loss hit for BUY position"""
        # Open BUY position
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),  # 50 pips SL
            take_profit=Decimal("1.1100"),
            risk_percent=1.0
        )
        
        self.assertEqual(position.status, Position.Status.OPEN)
        
        # Simulate SL hit
        closing_price = Decimal("1.0950")  # Exactly at SL
        closed_position = close_trade(
            position_id=position.id,
            closing_price=closing_price
        )
        
        self.assertEqual(closed_position.status, Position.Status.CLOSED)
        self.assertIsNotNone(closed_position.pnl)
        self.assertLess(closed_position.pnl, Decimal("0"))  # Loss
    
    def test_tp_hit_sell(self):
        """Test take profit hit for SELL position"""
        # Open SELL position
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.SELL,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.1050"),  # 50 pips SL
            take_profit=Decimal("1.0900"),  # 100 pips TP
            risk_percent=1.0
        )
        
        # Simulate TP hit
        closing_price = Decimal("1.0900")  # Exactly at TP
        closed_position = close_trade(
            position_id=position.id,
            closing_price=closing_price
        )
        
        self.assertEqual(closed_position.status, Position.Status.CLOSED)
        self.assertIsNotNone(closed_position.pnl)
        self.assertGreater(closed_position.pnl, Decimal("0"))  # Profit
    
    def test_partial_close(self):
        """Test partial close functionality"""
        # Open position
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        original_size = position.position_size
        
        # Partial close (50%)
        partial_size = original_size / Decimal("2")
        closed_position = close_trade(
            position_id=position.id,
            closing_price=Decimal("1.1050"),
            close_size=partial_size
        )
        
        self.assertEqual(closed_position.status, Position.Status.PARTIAL)
        self.assertIsNotNone(closed_position.remaining_size)
        self.assertAlmostEqual(
            float(closed_position.remaining_size),
            float(partial_size),
            places=4
        )
        
        # Close remaining
        final_position = close_trade(
            position_id=position.id,
            closing_price=Decimal("1.1050")
        )
        
        self.assertEqual(final_position.status, Position.Status.CLOSED)
        self.assertEqual(final_position.remaining_size, Decimal("0"))
    
    def test_gap_spike_handling(self):
        """Test gap/spike price handling"""
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Simulate gap/spike (price jumps far beyond SL)
        gap_price = Decimal("1.0900")  # 100 pips gap
        
        # Should still close correctly
        closed_position = close_trade(
            position_id=position.id,
            closing_price=gap_price
        )
        
        self.assertEqual(closed_position.status, Position.Status.CLOSED)
        # PnL should reflect the gap
        self.assertLess(closed_position.pnl, Decimal("0"))
    
    def test_one_dollar_balance(self):
        """Test trading with $1 balance (edge case)"""
        # Open trade with minimal balance
        position = open_trade(
            account=self.demo_account,  # $1 balance
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,  # Ultra calm for minimal risk
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=0.5  # Very small risk
        )
        
        self.assertIsNotNone(position)
        self.assertGreater(position.position_size, Decimal("0"))
        
        # Close trade
        closed_position = close_trade(
            position_id=position.id,
            closing_price=Decimal("1.1050")
        )
        
        self.assertEqual(closed_position.status, Position.Status.CLOSED)
    
    def test_double_close_prevention(self):
        """Test that position cannot be closed twice"""
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # First close
        close_trade(
            position_id=position.id,
            closing_price=Decimal("1.1050")
        )
        
        # Second close should fail
        with self.assertRaises(ValueError):
            close_trade(
                position_id=position.id,
                closing_price=Decimal("1.1050")
            )
    
    def test_pnl_calculation_buy(self):
        """Test PnL calculation for BUY"""
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Calculate PnL at different prices
        pnl_profit = PnLEngine.calculate_pnl(position, Decimal("1.1100"))
        self.assertGreater(pnl_profit, Decimal("0"))
        
        pnl_loss = PnLEngine.calculate_pnl(position, Decimal("1.0900"))
        self.assertLess(pnl_loss, Decimal("0"))
    
    def test_pnl_calculation_sell(self):
        """Test PnL calculation for SELL"""
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.SELL,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.1050"),
            risk_percent=1.0
        )
        
        # Calculate PnL at different prices
        pnl_profit = PnLEngine.calculate_pnl(position, Decimal("1.0900"))
        self.assertGreater(pnl_profit, Decimal("0"))
        
        pnl_loss = PnLEngine.calculate_pnl(position, Decimal("1.1100"))
        self.assertLess(pnl_loss, Decimal("0"))
    
    def test_unrealized_pnl(self):
        """Test unrealized PnL calculation"""
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Update unrealized PnL
        current_price = Decimal("1.1050")
        PnLEngine.update_position_pnl(position, current_price)
        
        position.refresh_from_db()
        self.assertIsNotNone(position.unrealized_pnl)
        self.assertGreater(position.unrealized_pnl, Decimal("0"))
    
    def test_stop_loss_mandatory(self):
        """Test that stop loss is mandatory"""
        with self.assertRaises(ValueError):
            open_trade(
                account=self.real_account,
                instrument=self.eurusd,
                side=Position.Side.BUY,
                mode=Position.Mode.SEMI,
                entry_price=Decimal("1.1000"),
                stop_loss=None,  # Missing SL
                risk_percent=1.0
            )
    
    def test_take_profit_optional(self):
        """Test that take profit is optional"""
        position = open_trade(
            account=self.real_account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=None,  # Optional
            risk_percent=1.0
        )
        
        self.assertIsNone(position.take_profit)
        self.assertEqual(position.status, Position.Status.OPEN)
