"""
Tests for Trade History Logging
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from trading.models import TradeAccount, Instrument, Position, PositionLog
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from trading.engine.logging import TradeLogger
from common.enums import TradeEvent

User = get_user_model()


class TradeLoggingTest(TestCase):
    """Test trade logging functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        
        self.account = TradeAccount.objects.create(
            user=self.user,
            account_type="demo",
            balance=Decimal("1000.00"),
            equity=Decimal("1000.00"),
            max_risk_per_trade=2.0,
            max_daily_loss=5.0
        )
        
        self.eurusd = Instrument.objects.create(
            symbol="EURUSD",
            is_halal=True,
            is_crypto=False,
            min_stop_distance=Decimal("0.0001")
        )
    
    def test_log_open_event(self):
        """Test logging trade open event"""
        position = open_trade(
            account=self.account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Check log was created
        logs = PositionLog.objects.filter(position=position, event_type=TradeEvent.OPEN)
        self.assertEqual(logs.count(), 1)
        
        log = logs.first()
        self.assertEqual(log.price, Decimal("1.1000"))
        self.assertEqual(log.size, position.position_size)
        self.assertIn("side", log.metadata)
        self.assertIn("mode", log.metadata)
    
    def test_log_close_event(self):
        """Test logging trade close event"""
        position = open_trade(
            account=self.account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Close trade
        closed_position = close_trade(
            position_id=position.id,
            closing_price=Decimal("1.1050")
        )
        
        # Check log was created
        logs = PositionLog.objects.filter(position=position, event_type=TradeEvent.CLOSE)
        self.assertEqual(logs.count(), 1)
        
        log = logs.first()
        self.assertEqual(log.price, Decimal("1.1050"))
        self.assertIsNotNone(log.pnl)
    
    def test_log_sl_hit(self):
        """Test logging stop loss hit"""
        position = open_trade(
            account=self.account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Close at SL
        close_trade(
            position_id=position.id,
            closing_price=Decimal("1.0950")  # Exactly at SL
        )
        
        # Check SL_HIT log
        logs = PositionLog.objects.filter(position=position, event_type=TradeEvent.SL_HIT)
        self.assertEqual(logs.count(), 1)
    
    def test_log_partial_close(self):
        """Test logging partial close"""
        position = open_trade(
            account=self.account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Partial close
        partial_size = position.position_size / Decimal("2")
        close_trade(
            position_id=position.id,
            closing_price=Decimal("1.1050"),
            close_size=partial_size
        )
        
        # Check PARTIAL log
        logs = PositionLog.objects.filter(position=position, event_type=TradeEvent.PARTIAL)
        self.assertEqual(logs.count(), 1)
        
        log = logs.first()
        self.assertEqual(log.size, partial_size)
