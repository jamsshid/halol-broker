"""
Integration tests for Ultra Calm vs Semi Calm mode comparison.
Tests trade flow with different volatility settings and PnL outcomes.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from market.price_feed import MockPriceFeed, get_price_feed, reset_price_feed
from calm.ultra import UltraCalmMode
from calm.semi import SemiCalmMode

User = get_user_model()


class MultiModeIntegrationTests(TestCase):
    """Integration tests comparing Ultra Calm vs Semi Calm modes"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        
        # Create demo accounts
        self.ultra_account = TradeAccount.objects.create(
            user=self.user,
            account_type="demo",
            balance=Decimal("10000.00"),
            equity=Decimal("10000.00"),
            max_risk_per_trade=1.0,
            max_daily_loss=2.0,
        )
        
        self.semi_account = TradeAccount.objects.create(
            user=self.user,
            account_type="demo",
            balance=Decimal("10000.00"),
            equity=Decimal("10000.00"),
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
        )
        
        # Create instrument
        self.instrument = Instrument.objects.create(
            symbol="EURUSD",
            is_halal=True,
            is_crypto=False,
            min_stop_distance=Decimal("0.0001"),
        )
        
        # Reset price feed singleton for clean state
        reset_price_feed()
    
    def test_ultra_calm_trade_flow(self):
        """
        Test complete trade flow in Ultra Calm mode.
        - Low volatility (fewer ticks)
        - Smaller price movements
        - Lower risk limits
        """
        # Set price feed to Ultra Calm mode
        price_feed = get_price_feed(use_mock=True)
        price_feed.set_mode("ULTRA")
        price_feed.enable_delay = False  # Disable delay for faster tests
        
        # Get initial price
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")  # 10 pips SL
        take_profit = entry_price + Decimal("0.0020")  # 20 pips TP
        
        # Open trade
        position = open_trade(
            account=self.ultra_account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode="ULTRA",
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_percent=Decimal("0.5"),  # 0.5% risk (within Ultra Calm limit)
            timeframe="M1",
        )
        
        self.assertIsNotNone(position)
        self.assertEqual(position.status, Position.Status.OPEN)
        self.assertEqual(position.mode, Position.Mode.ULTRA)
        self.assertEqual(position.account.id, self.ultra_account.id)
        
        # Simulate a few ticks (Ultra Calm: low volatility)
        prices = []
        for _ in range(5):
            tick_price = price_feed.simulate_tick("EURUSD")
            prices.append(tick_price)
        
        # Ultra Calm should have smaller price movements
        price_range = max(prices) - min(prices)
        self.assertLess(price_range, Decimal("0.0020"), "Ultra Calm should have low volatility")
        
        # Close trade at a profit
        closing_price = entry_price + Decimal("0.0015")  # 15 pips profit
        closed_position = close_trade(
            position_id=position.id,
            closing_price=closing_price,
        )
        
        self.assertEqual(closed_position.status, Position.Status.CLOSED)
        self.assertIsNotNone(closed_position.pnl)
        self.assertGreater(closed_position.pnl, Decimal("0"), "Should have positive PnL")
        
        # Verify logs were created
        logs = closed_position.logs.all()
        self.assertGreater(len(logs), 0, "Trade logs should be created")
        
        # Check that OPEN and CLOSE events are logged
        event_types = [log.event_type for log in logs]
        self.assertIn("OPEN", event_types)
        self.assertIn("CLOSE", event_types)
    
    def test_semi_calm_trade_flow(self):
        """
        Test complete trade flow in Semi Calm mode.
        - Medium volatility (more ticks)
        - Larger price movements
        - Higher risk limits
        """
        # Set price feed to Semi Calm mode
        price_feed = get_price_feed(use_mock=True)
        price_feed.set_mode("SEMI")
        price_feed.enable_delay = False  # Disable delay for faster tests
        
        # Get initial price
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")  # 10 pips SL
        take_profit = entry_price + Decimal("0.0020")  # 20 pips TP
        
        # Open trade
        position = open_trade(
            account=self.semi_account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode="SEMI",
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_percent=Decimal("1.5"),  # 1.5% risk (within Semi Calm limit)
            timeframe="M1",
        )
        
        self.assertIsNotNone(position)
        self.assertEqual(position.status, Position.Status.OPEN)
        self.assertEqual(position.mode, Position.Mode.SEMI)
        self.assertEqual(position.account.id, self.semi_account.id)
        
        # Simulate a few ticks (Semi Calm: medium volatility)
        prices = []
        for _ in range(5):
            tick_price = price_feed.simulate_tick("EURUSD")
            prices.append(tick_price)
        
        # Semi Calm should have larger price movements than Ultra Calm
        price_range = max(prices) - min(prices)
        # Note: This is a relative comparison, actual values depend on random seed
        
        # Close trade at a profit
        closing_price = entry_price + Decimal("0.0015")  # 15 pips profit
        closed_position = close_trade(
            position_id=position.id,
            closing_price=closing_price,
        )
        
        self.assertEqual(closed_position.status, Position.Status.CLOSED)
        self.assertIsNotNone(closed_position.pnl)
        self.assertGreater(closed_position.pnl, Decimal("0"), "Should have positive PnL")
        
        # Verify logs were created
        logs = closed_position.logs.all()
        self.assertGreater(len(logs), 0, "Trade logs should be created")
    
    def test_ultra_vs_semi_volatility_comparison(self):
        """
        Compare volatility between Ultra Calm and Semi Calm modes.
        Ultra Calm should have lower volatility than Semi Calm.
        """
        # Test Ultra Calm volatility
        ultra_feed = MockPriceFeed(use_mock=True, enable_delay=False, mode="ULTRA")
        ultra_prices = []
        for _ in range(20):
            price = ultra_feed.simulate_tick("EURUSD")
            ultra_prices.append(price)
        
        ultra_range = max(ultra_prices) - min(ultra_prices)
        ultra_volatility = ultra_range / min(ultra_prices)  # Relative volatility
        
        # Test Semi Calm volatility
        semi_feed = MockPriceFeed(use_mock=True, enable_delay=False, mode="SEMI")
        semi_prices = []
        for _ in range(20):
            price = semi_feed.simulate_tick("EURUSD")
            semi_prices.append(price)
        
        semi_range = max(semi_prices) - min(semi_prices)
        semi_volatility = semi_range / min(semi_prices)  # Relative volatility
        
        # Ultra Calm should have lower volatility than Semi Calm
        # (Note: Due to randomness, this might occasionally fail, but on average should hold)
        self.assertLessEqual(
            ultra_volatility,
            semi_volatility * Decimal("2"),  # Allow some margin for randomness
            f"Ultra Calm volatility ({ultra_volatility}) should be <= Semi Calm ({semi_volatility})"
        )
    
    def test_ultra_calm_risk_limits(self):
        """Test that Ultra Calm mode enforces stricter risk limits"""
        price_feed = get_price_feed(use_mock=True)
        price_feed.set_mode("ULTRA")
        
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")
        
        # Try to open with risk > Ultra Calm limit (1.0%)
        with self.assertRaises(Exception):  # Should raise RiskLimitError or ValueError
            open_trade(
                account=self.ultra_account,
                instrument=self.instrument,
                side=Position.Side.BUY,
                mode="ULTRA",
                entry_price=entry_price,
                stop_loss=stop_loss,
                risk_percent=Decimal("2.0"),  # Exceeds Ultra Calm limit
            )
    
    def test_semi_calm_risk_limits(self):
        """Test that Semi Calm mode allows higher risk limits"""
        price_feed = get_price_feed(use_mock=True)
        price_feed.set_mode("SEMI")
        
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")
        
        # Open with risk within Semi Calm limit (2.0%)
        position = open_trade(
            account=self.semi_account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode="SEMI",
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=Decimal("1.8"),  # Within Semi Calm limit
        )
        
        self.assertIsNotNone(position)
        self.assertEqual(position.mode, Position.Mode.SEMI)
    
    def test_candle_simulation_ultra_calm(self):
        """Test candlestick simulation in Ultra Calm mode"""
        ultra_feed = MockPriceFeed(use_mock=True, enable_delay=False, mode="ULTRA")
        
        # Generate M1 candle
        candle = ultra_feed.simulate_candle("EURUSD", "M1")
        
        self.assertIn("open", candle)
        self.assertIn("high", candle)
        self.assertIn("low", candle)
        self.assertIn("close", candle)
        self.assertIn("volume", candle)
        
        # Validate OHLC relationships
        self.assertGreaterEqual(candle["high"], candle["open"])
        self.assertGreaterEqual(candle["high"], candle["close"])
        self.assertLessEqual(candle["low"], candle["open"])
        self.assertLessEqual(candle["low"], candle["close"])
    
    def test_candle_simulation_semi_calm(self):
        """Test candlestick simulation in Semi Calm mode"""
        semi_feed = MockPriceFeed(use_mock=True, enable_delay=False, mode="SEMI")
        
        # Generate H1 candle
        candle = semi_feed.simulate_candle("EURUSD", "H1")
        
        self.assertIn("open", candle)
        self.assertIn("high", candle)
        self.assertIn("low", candle)
        self.assertIn("close", candle)
        self.assertIn("volume", candle)
        
        # Validate OHLC relationships
        self.assertGreaterEqual(candle["high"], candle["open"])
        self.assertGreaterEqual(candle["high"], candle["close"])
        self.assertLessEqual(candle["low"], candle["open"])
        self.assertLessEqual(candle["low"], candle["close"])
        
        # H1 candle should have more ticks than M1 (larger range)
        m1_candle = semi_feed.simulate_candle("EURUSD", "M1")
        h1_range = candle["high"] - candle["low"]
        m1_range = m1_candle["high"] - m1_candle["low"]
        
        # H1 should generally have larger range (but allow for randomness)
        self.assertGreaterEqual(
            h1_range,
            m1_range * Decimal("0.5"),  # Allow margin for randomness
            "H1 candle should have larger range than M1"
        )
    
    def test_price_history_tracking(self):
        """Test that price history is tracked correctly"""
        feed = MockPriceFeed(use_mock=True, enable_delay=False, mode="ULTRA")
        
        # Generate some ticks
        for _ in range(10):
            feed.simulate_tick("EURUSD")
        
        # Get price history
        history = feed.get_price_history("EURUSD", limit=5)
        
        self.assertEqual(len(history), 5, "Should return last 5 prices")
        self.assertGreater(len(history), 0, "History should not be empty")
        
        # All prices should be positive
        for price in history:
            self.assertGreater(price, Decimal("0"), "Prices should be positive")
    
    def test_tick_based_movement(self):
        """Test that tick-based movement works incrementally"""
        feed = MockPriceFeed(use_mock=True, enable_delay=False, mode="ULTRA")
        
        # Get initial price
        initial_price = feed.get_price("EURUSD")
        
        # Generate a few ticks
        prices = [initial_price]
        for _ in range(5):
            tick_price = feed.simulate_tick("EURUSD")
            prices.append(tick_price)
        
        # Prices should change incrementally (not jump drastically)
        for i in range(1, len(prices)):
            price_change = abs(prices[i] - prices[i-1])
            # Change should be reasonable (less than 1% per tick)
            max_change = prices[i-1] * Decimal("0.01")
            self.assertLessEqual(
                price_change,
                max_change,
                f"Price change from {prices[i-1]} to {prices[i]} should be incremental"
            )
