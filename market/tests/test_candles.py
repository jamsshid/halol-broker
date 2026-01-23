"""
Tests for Candlestick Data Aggregation
"""
from django.test import TestCase
from datetime import datetime, timedelta
from market.services.candles import CandlestickService
from common.enums import Timeframe


class CandlestickServiceTest(TestCase):
    """Test candlestick data generation"""
    
    def test_generate_candlestick_basic(self):
        """Test basic candlestick generation"""
        candles = CandlestickService.generate_candlestick(
            symbol="EURUSD",
            timeframe=Timeframe.H1,
            limit=10
        )
        
        self.assertEqual(len(candles), 10)
        
        # Check structure
        candle = candles[0]
        self.assertIn("time", candle)
        self.assertIn("open", candle)
        self.assertIn("high", candle)
        self.assertIn("low", candle)
        self.assertIn("close", candle)
        self.assertIn("volume", candle)
        
        # Check OHLC values
        self.assertGreater(candle["high"], candle["low"])
        self.assertGreaterEqual(candle["high"], candle["open"])
        self.assertGreaterEqual(candle["high"], candle["close"])
        self.assertLessEqual(candle["low"], candle["open"])
        self.assertLessEqual(candle["low"], candle["close"])
    
    def test_generate_candlestick_timeframe(self):
        """Test different timeframes"""
        for timeframe in [Timeframe.M1, Timeframe.M5, Timeframe.H1, Timeframe.D1]:
            candles = CandlestickService.generate_candlestick(
                symbol="BTCUSD",
                timeframe=timeframe,
                limit=5
            )
            
            self.assertEqual(len(candles), 5)
            self.assertIsInstance(candles[0]["time"], str)
    
    def test_get_latest_candle(self):
        """Test get latest candle"""
        candle = CandlestickService.get_latest_candle(
            symbol="EURUSD",
            timeframe=Timeframe.H1
        )
        
        self.assertIsNotNone(candle)
        self.assertIn("time", candle)
        self.assertIn("close", candle)
    
    def test_candlestick_with_time_range(self):
        """Test candlestick with time range"""
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        candles = CandlestickService.generate_candlestick(
            symbol="EURUSD",
            timeframe=Timeframe.H1,
            start_time=start_time,
            end_time=end_time,
            limit=100
        )
        
        self.assertGreater(len(candles), 0)
        self.assertLessEqual(len(candles), 100)
