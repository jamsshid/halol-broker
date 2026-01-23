"""
Flutter Hooks Integration Tests
Tests Flutter-friendly event hooks and payload structure.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock

from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.services.trade_close import close_trade
from trading.hooks import (
    on_trade_open,
    on_trade_close,
    on_sl_hit,
    on_tp_hit,
    on_pnl_update,
)
from common.enums import Timeframe

User = get_user_model()


class FlutterHooksTest(TestCase):
    """Test Flutter hooks integration"""
    
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
    
    def test_on_trade_open_hook_payload(self):
        """Test on_trade_open hook returns Flutter-friendly payload"""
        position = Position.objects.create(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0,
            position_size=Decimal("1.0"),
            status=Position.Status.OPEN,
        )
        
        payload = on_trade_open(position, self.account, Decimal("1.1000"))
        
        # Verify payload structure
        self.assertEqual(payload["event_type"], "TRADE_OPENED")
        self.assertEqual(payload["position_id"], str(position.id))
        self.assertEqual(payload["account_id"], str(self.account.id))
        self.assertEqual(payload["user_id"], self.user.id)
        self.assertEqual(payload["symbol"], "EURUSD")
        self.assertEqual(payload["side"], "BUY")
        self.assertEqual(payload["mode"], "ULTRA")
        self.assertIn("timestamp", payload)
        self.assertIn("entry_price", payload)
        self.assertIn("stop_loss", payload)
    
    @patch('trading.hooks.flutter_hooks.notify')
    def test_on_trade_open_calls_notify(self, mock_notify):
        """Test on_trade_open calls notify function"""
        position = Position.objects.create(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0,
            position_size=Decimal("1.0"),
            status=Position.Status.OPEN,
        )
        
        on_trade_open(position, self.account, Decimal("1.1000"))
        
        # Verify notify was called
        mock_notify.assert_called_once()
        call_args = mock_notify.call_args
        self.assertEqual(call_args.kwargs['event_type'], "TRADE_OPENED")
        self.assertIn("payload", call_args.kwargs)
    
    def test_on_trade_close_hook_payload(self):
        """Test on_trade_close hook returns Flutter-friendly payload"""
        position = Position.objects.create(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0,
            position_size=Decimal("1.0"),
            remaining_size=Decimal("1.0"),
            status=Position.Status.OPEN,
        )
        
        payload = on_trade_close(
            position,
            self.account,
            Decimal("1.1050"),
            Decimal("50.00"),
            Decimal("1.0")
        )
        
        # Verify payload structure
        self.assertEqual(payload["event_type"], "TRADE_CLOSED")
        self.assertEqual(payload["closing_price"], "1.1050")
        self.assertEqual(payload["pnl"], "50.00")
        self.assertIn("is_partial", payload)
        self.assertIn("remaining_size", payload)
    
    def test_on_sl_hit_hook_payload(self):
        """Test on_sl_hit hook returns Flutter-friendly payload"""
        position = Position.objects.create(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0,
            position_size=Decimal("1.0"),
            status=Position.Status.OPEN,
        )
        
        payload = on_sl_hit(
            position,
            self.account,
            Decimal("1.0950"),
            Decimal("-50.00")
        )
        
        # Verify payload structure
        self.assertEqual(payload["event_type"], "SL_HIT")
        self.assertEqual(payload["closing_price"], "1.0950")
        self.assertEqual(payload["stop_loss"], "1.0950")
        self.assertEqual(payload["pnl"], "-50.00")
    
    def test_on_tp_hit_hook_payload(self):
        """Test on_tp_hit hook returns Flutter-friendly payload"""
        position = Position.objects.create(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1100"),
            risk_percent=1.0,
            position_size=Decimal("1.0"),
            status=Position.Status.OPEN,
        )
        
        payload = on_tp_hit(
            position,
            self.account,
            Decimal("1.1100"),
            Decimal("100.00")
        )
        
        # Verify payload structure
        self.assertEqual(payload["event_type"], "TP_HIT")
        self.assertEqual(payload["closing_price"], "1.1100")
        self.assertEqual(payload["take_profit"], "1.1100")
        self.assertEqual(payload["pnl"], "100.00")
    
    def test_on_pnl_update_hook_payload(self):
        """Test on_pnl_update hook returns Flutter-friendly payload"""
        position = Position.objects.create(
            account=self.account,
            instrument=self.instrument,
            side=Position.Side.BUY,
            mode=Position.Mode.ULTRA,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            risk_percent=1.0,
            position_size=Decimal("1.0"),
            status=Position.Status.OPEN,
        )
        
        payload = on_pnl_update(
            position,
            self.account,
            Decimal("25.00"),
            Decimal("1.1025")
        )
        
        # Verify payload structure
        self.assertEqual(payload["event_type"], "PNL_UPDATE")
        self.assertEqual(payload["unrealized_pnl"], "25.00")
        self.assertEqual(payload["current_price"], "1.1025")
        self.assertIn("pnl_percent", payload)
    
    def test_hooks_called_during_trade_open(self):
        """Test that Flutter hooks are called during trade open"""
        with patch('trading.hooks.flutter_hooks.on_trade_open') as mock_hook:
            from market.price_feed import get_price_feed, reset_price_feed
            reset_price_feed()
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
            
            # Verify hook was called
            mock_hook.assert_called_once()
            call_args = mock_hook.call_args
            self.assertEqual(call_args[0][0], position)
            self.assertEqual(call_args[0][1], self.account)
    
    def test_hooks_called_during_trade_close(self):
        """Test that Flutter hooks are called during trade close"""
        from market.price_feed import get_price_feed, reset_price_feed
        reset_price_feed()
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
        
        with patch('trading.hooks.flutter_hooks.on_trade_close') as mock_hook:
            closing_price = price_feed.get_price("EURUSD")
            close_trade(
                position_id=position.id,
                closing_price=closing_price
            )
            
            # Verify hook was called
            mock_hook.assert_called_once()
