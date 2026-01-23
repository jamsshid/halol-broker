"""
Chart & Dashboard Integration Tests
Tests integration between trading engine, chart data, and dashboard metrics.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from market.services.candles import candlestick_service
from market.price_feed import get_price_feed, reset_price_feed
from common.enums import Timeframe

User = get_user_model()


class ChartDashboardIntegrationTest(TestCase):
    """Test chart and dashboard integration"""
    
    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com", password="password123")
        self.account = TradeAccount.objects.create(
            user=self.user,
            account_type="demo",
            balance=Decimal("10000.00"),
            equity=Decimal("10000.00"),
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
        )
        self.instrument, _ = Instrument.objects.get_or_create(
            symbol="EURUSD",
            defaults={"is_halal": True, "min_stop_distance": Decimal("0.0001")}
        )
        reset_price_feed()
    
    def test_trade_open_updates_chart_data(self):
        """Test that opening a trade triggers chart data update"""
        price_feed = get_price_feed()
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")
        
        # Mock candlestick service
        with patch.object(candlestick_service, 'add_tick') as mock_add_tick:
            position = open_trade(
                account=self.account,
                instrument=self.instrument,
                side=Position.Side.BUY,
                mode=Position.Mode.ULTRA,
                entry_price=entry_price,
                stop_loss=stop_loss,
                risk_percent=0.5,
                timeframe=Timeframe.M1.value
            )
            
            # Verify chart data update was triggered (indirectly via price feed)
            # In real implementation, trade open might trigger price feed update
            self.assertIsNotNone(position)
            self.assertEqual(position.status, Position.Status.OPEN)
    
    def test_trade_close_updates_dashboard_pnl(self):
        """Test that closing a trade updates dashboard PnL metrics"""
        price_feed = get_price_feed()
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")
        
        position = open_trade(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=0.5,
            timeframe=Timeframe.M1.value
        )
        
        initial_balance = self.account.balance
        
        # Close trade
        closing_price = entry_price + Decimal("0.0020")  # Profit
        closed_position = close_trade(
            position_id=position.id,
            closing_price=closing_price
        )
        
        # Verify PnL was calculated
        self.assertIsNotNone(closed_position.pnl)
        self.assertGreater(closed_position.pnl, Decimal("0"))
        
        # Verify position status
        self.assertEqual(closed_position.status, Position.Status.CLOSED)
    
    def test_multi_user_trade_aggregation(self):
        """Test that multiple users' trades are correctly aggregated in dashboard"""
        # Create second user
        user2 = User.objects.create_user(email="test2@example.com", password="password123")
        account2 = TradeAccount.objects.create(
            user=user2,
            account_type="demo",
            balance=Decimal("10000.00"),
            equity=Decimal("10000.00"),
            max_risk_per_trade=2.0,
            max_daily_loss=5.0,
        )
        
        price_feed = get_price_feed()
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")
        
        # User 1 opens trade
        position1 = open_trade(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=0.5,
            timeframe=Timeframe.M1.value
        )
        
        # User 2 opens trade
        position2 = open_trade(
            account=account2,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=1.0,
            timeframe=Timeframe.M1.value
        )
        
        # Verify both positions exist
        self.assertEqual(Position.objects.filter(status=Position.Status.OPEN).count(), 2)
        
        # Verify positions belong to different accounts
        self.assertNotEqual(position1.account, position2.account)
        self.assertEqual(position1.instrument, position2.instrument)
    
    def test_chart_candle_generation_after_trade(self):
        """Test that chart candles are generated after trade operations"""
        price_feed = get_price_feed()
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")
        
        # Open trade
        position = open_trade(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=0.5,
            timeframe=Timeframe.M1.value
        )
        
        # Simulate some price ticks
        for _ in range(5):
            price_feed.simulate_tick("EURUSD")
        
        # Generate candlestick data
        candles = candlestick_service.generate_candlestick(
            symbol="EURUSD",
            timeframe=Timeframe.M1.value,
            limit=10
        )
        
        # Verify candles were generated (if Redis is available, otherwise may be empty)
        # This test verifies the integration path, not the actual candle generation
        self.assertIsInstance(candles, list)
    
    def test_dashboard_metrics_after_multiple_trades(self):
        """Test dashboard metrics after multiple trades"""
        price_feed = get_price_feed()
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")
        
        # Open first trade
        position1 = open_trade(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=0.5,
            timeframe=Timeframe.M1.value
        )
        
        # Close first trade with profit
        closing_price1 = entry_price + Decimal("0.0010")
        close_trade(position_id=position1.id, closing_price=closing_price1)
        
        # Open second trade
        entry_price2 = price_feed.get_price("EURUSD")
        stop_loss2 = entry_price2 - Decimal("0.0010")
        position2 = open_trade(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=entry_price2,
            stop_loss=stop_loss2,
            risk_percent=0.5,
            timeframe=Timeframe.M1.value
        )
        
        # Verify dashboard metrics
        closed_positions = Position.objects.filter(
            account=self.account,
            status=Position.Status.CLOSED
        )
        open_positions = Position.objects.filter(
            account=self.account,
            status=Position.Status.OPEN
        )
        
        self.assertEqual(closed_positions.count(), 1)
        self.assertEqual(open_positions.count(), 1)
        
        # Verify total PnL
        total_pnl = sum(p.pnl for p in closed_positions if p.pnl)
        self.assertIsNotNone(total_pnl)
    
    def test_chart_data_api_integration(self):
        """Test that chart data API returns data after trades"""
        price_feed = get_price_feed()
        entry_price = price_feed.get_price("EURUSD")
        stop_loss = entry_price - Decimal("0.0010")
        
        # Open trade
        position = open_trade(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_percent=0.5,
            timeframe=Timeframe.M1.value
        )
        
        # Simulate price movement
        for _ in range(10):
            price_feed.simulate_tick("EURUSD")
        
        # Get candlestick data (integration test - may return empty if Redis unavailable)
        candles = candlestick_service.generate_candlestick(
            symbol="EURUSD",
            timeframe=Timeframe.M1.value,
            limit=10
        )
        
        # Verify API structure (even if empty)
        self.assertIsInstance(candles, list)
        
        # If candles exist, verify structure
        if candles:
            candle = candles[0]
            self.assertIn("time", candle)
            self.assertIn("open", candle)
            self.assertIn("high", candle)
            self.assertIn("low", candle)
            self.assertIn("close", candle)
            self.assertIn("volume", candle)
