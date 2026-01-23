"""
Tests for Trade Notifications & Hooks
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from common.hooks import notify, notify_trade_opened, notify_trade_closed
from unittest.mock import patch

User = get_user_model()


class NotificationHooksTest(TestCase):
    """Test notification hooks"""
    
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
    
    @patch('common.hooks.trade_notification.send')
    def test_notify_function(self, mock_signal):
        """Test notify function sends signal"""
        notify(
            event_type="TEST_EVENT",
            payload={"test": "data"},
            user_id=self.user.id
        )
        
        # Check signal was sent
        mock_signal.assert_called_once()
        call_args = mock_signal.call_args
        self.assertEqual(call_args.kwargs['event_type'], "TEST_EVENT")
        self.assertEqual(call_args.kwargs['user_id'], self.user.id)
    
    @patch('common.hooks.notify')
    def test_notify_trade_opened(self, mock_notify):
        """Test trade opened notification"""
        position = open_trade(
            account=self.account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Check notification was called
        mock_notify.assert_called()
        call_args = mock_notify.call_args
        self.assertEqual(call_args.kwargs['event_type'], "TRADE_OPENED")
    
    @patch('common.hooks.notify')
    def test_notify_trade_closed(self, mock_notify):
        """Test trade closed notification"""
        position = open_trade(
            account=self.account,
            instrument=self.eurusd,
            side=Position.Side.BUY,
            mode=Position.Mode.SEMI,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0
        )
        
        # Reset mock
        mock_notify.reset_mock()
        
        # Close trade
        close_trade(
            position_id=position.id,
            closing_price=Decimal("1.1050")
        )
        
        # Check notification was called
        mock_notify.assert_called()
        call_args = mock_notify.call_args
        self.assertIn(call_args.kwargs['event_type'], ["TRADE_CLOSED", "TP_HIT", "SL_HIT"])
