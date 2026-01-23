"""
Redis Integration Tests
Tests for Redis caching, SL/TP watcher, and calm mode state.
"""
from decimal import Decimal
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone

from market.redis_cache import MarketPriceCache, price_cache
from market.services.candles import CandlestickService, candlestick_service
from market.sl_tp_watcher import SLTPWatcher, sl_tp_watcher
from calm.helpers import CalmStateCache, calm_state_cache


class RedisIntegrationTestCase(TestCase):
    """Base test case with Redis mocking"""

    def setUp(self):
        # Mock Redis client for all tests
        self.redis_mock = Mock()
        with patch('market.redis_cache.price_cache.redis_client', self.redis_mock), \
             patch('market.services.candles.candlestick_service.redis_client', self.redis_mock), \
             patch('market.sl_tp_watcher.sl_tp_watcher.price_cache.redis_client', self.redis_mock), \
             patch('calm.helpers.calm_state_cache.redis_client', self.redis_mock):
            pass


class MarketPriceCacheTest(RedisIntegrationTestCase):
    """Test market price cache functionality"""

    def test_set_price_success(self):
        """Test successful price setting"""
        self.redis_mock.setex.return_value = True

        result = price_cache.set_price('EURUSD', Decimal('1.0500'))
        self.assertTrue(result)
        self.redis_mock.setex.assert_called_once()

    def test_set_price_with_metadata(self):
        """Test price setting with metadata"""
        metadata = {'volume': 1000, 'timestamp': '2024-01-01T10:00:00Z'}
        self.redis_mock.setex.return_value = True

        result = price_cache.set_price('EURUSD', Decimal('1.0500'), metadata)
        self.assertTrue(result)

        # Check that metadata was included
        call_args = self.redis_mock.setex.call_args
        stored_data = call_args[0][2]  # Third argument is the data
        self.assertIn('volume', stored_data)
        self.assertIn('timestamp', stored_data)

    def test_get_price_success(self):
        """Test successful price retrieval"""
        mock_data = '{"price": "1.0500", "bid": "1.0498", "ask": "1.0502"}'
        self.redis_mock.get.return_value = mock_data

        result = price_cache.get_price('EURUSD')
        self.assertIsNotNone(result)
        self.assertEqual(Decimal(result['price']), Decimal('1.0500'))

    def test_get_price_not_found(self):
        """Test price retrieval when not found"""
        self.redis_mock.get.return_value = None

        result = price_cache.get_price('EURUSD')
        self.assertIsNone(result)

    def test_redis_failure_fallback(self):
        """Test fallback when Redis fails"""
        # Simulate Redis failure
        price_cache.redis_client = None

        # Should not raise exception
        result = price_cache.set_price('EURUSD', Decimal('1.0500'))
        self.assertFalse(result)  # Should return False gracefully


class CandlestickServiceTest(RedisIntegrationTestCase):
    """Test candlestick aggregation with Redis"""

    def test_add_tick_success(self):
        """Test successful tick addition"""
        self.redis_mock.zadd.return_value = 1
        self.redis_mock.expire.return_value = True

        result = candlestick_service.add_tick('EURUSD', Decimal('1.0500'), Decimal('100'))
        self.assertTrue(result)
        self.redis_mock.zadd.assert_called_once()

    def test_generate_candlesticks_with_redis(self):
        """Test candlestick generation using Redis data"""
        # Mock Redis responses
        self.redis_mock.keys.return_value = []
        self.redis_mock.zrangebyscore.return_value = []

        # Should fall back to mock data generation
        candles = candlestick_service.generate_candlestick('EURUSD', 'M1', limit=5)
        self.assertIsInstance(candles, list)
        self.assertGreater(len(candles), 0)

    def test_redis_failure_fallback(self):
        """Test fallback when Redis fails during candlestick generation"""
        candlestick_service.redis_client = None

        # Should generate mock data
        candles = candlestick_service.generate_candlestick('EURUSD', 'M1', limit=5)
        self.assertIsInstance(candles, list)
        self.assertGreater(len(candles), 0)


class SLTPWatcherTest(RedisIntegrationTestCase):
    """Test SL/TP watcher functionality"""

    def setUp(self):
        super().setUp()
        # Create mock position
        self.mock_position = Mock()
        self.mock_position.id = 1
        self.mock_position.side = 'BUY'
        self.mock_position.stop_loss = Decimal('1.0400')
        self.mock_position.take_profit = Decimal('1.0600')
        self.mock_position.instrument.symbol = 'EURUSD'

    @patch('market.redis_cache.price_cache.get_price_value')
    def test_check_single_position_sl_hit(self, mock_get_price):
        """Test SL hit detection"""
        mock_get_price.return_value = Decimal('1.0350')  # Below SL

        result = sl_tp_watcher._check_single_position(self.mock_position)
        self.assertEqual(result, 'sl')

    @patch('market.redis_cache.price_cache.get_price_value')
    def test_check_single_position_tp_hit(self, mock_get_price):
        """Test TP hit detection"""
        mock_get_price.return_value = Decimal('1.0650')  # Above TP

        result = sl_tp_watcher._check_single_position(self.mock_position)
        self.assertEqual(result, 'tp')

    @patch('market.redis_cache.price_cache.get_price_value')
    def test_check_single_position_no_hit(self, mock_get_price):
        """Test no hit when price is between SL and TP"""
        mock_get_price.return_value = Decimal('1.0500')

        result = sl_tp_watcher._check_single_position(self.mock_position)
        self.assertIsNone(result)

    @patch('market.redis_cache.price_cache.get_price_value')
    def test_check_single_position_no_price(self, mock_get_price):
        """Test when no price is available"""
        mock_get_price.return_value = None

        result = sl_tp_watcher._check_single_position(self.mock_position)
        self.assertIsNone(result)


class CalmStateCacheTest(RedisIntegrationTestCase):
    """Test calm mode state caching"""

    def test_set_stress_flag_success(self):
        """Test successful stress flag setting"""
        self.redis_mock.hset.return_value = 1
        self.redis_mock.expire.return_value = True

        result = calm_state_cache.set_stress_flag(1, True, 'ULTRA')
        self.assertTrue(result)
        self.redis_mock.hset.assert_called_once()

    def test_get_stress_flag_success(self):
        """Test successful stress flag retrieval"""
        mock_data = '{"stress_free": true, "mode": "ULTRA"}'
        self.redis_mock.hget.return_value = mock_data

        result = calm_state_cache.get_stress_flag(1)
        self.assertIsNotNone(result)
        self.assertTrue(result['stress_free'])
        self.assertEqual(result['mode'], 'ULTRA')

    def test_set_blurred_pnl_success(self):
        """Test successful blurred PnL setting"""
        self.redis_mock.hset.return_value = 1
        self.redis_mock.expire.return_value = True

        result = calm_state_cache.set_blurred_pnl(1, Decimal('100.50'), Decimal('95.25'))
        self.assertTrue(result)

    def test_get_blurred_pnl_success(self):
        """Test successful blurred PnL retrieval"""
        mock_data = '{"blurred_pnl": "100.50", "actual_pnl": "95.25"}'
        self.redis_mock.hget.return_value = mock_data

        result = calm_state_cache.get_blurred_pnl(1)
        self.assertIsNotNone(result)
        self.assertEqual(result['blurred_pnl'], Decimal('100.50'))
        self.assertEqual(result['actual_pnl'], Decimal('95.25'))

    def test_clear_position_state(self):
        """Test position state clearing"""
        self.redis_mock.delete.return_value = 1

        result = calm_state_cache.clear_position_state(1)
        self.assertTrue(result)
        self.redis_mock.delete.assert_called_once()

    def test_redis_failure_graceful(self):
        """Test graceful handling when Redis fails"""
        calm_state_cache.redis_client = None

        # Should not raise exceptions
        result = calm_state_cache.set_stress_flag(1, True, 'ULTRA')
        self.assertFalse(result)

        result = calm_state_cache.get_stress_flag(1)
        self.assertIsNone(result)


# Integration test for the complete flow
class RedisIntegrationFlowTest(TestCase):
    """Test the complete Redis integration flow"""

    @patch('market.redis_cache.price_cache.redis_client')
    @patch('market.services.candles.candlestick_service.redis_client')
    @patch('market.sl_tp_watcher.sl_tp_watcher.price_cache.redis_client')
    @patch('calm.helpers.calm_state_cache.redis_client')
    def test_system_continues_without_redis(self, calm_mock, sltp_mock, candles_mock, price_mock):
        """Test that system continues to function when Redis is unavailable"""
        # Simulate Redis failures
        price_mock.return_value = None
        candles_mock.return_value = None
        sltp_mock.return_value = None
        calm_mock.return_value = None

        # These should not raise exceptions
        price_result = price_cache.set_price('EURUSD', Decimal('1.0500'))
        self.assertFalse(price_result)

        candles = candlestick_service.generate_candlestick('EURUSD', 'M1', limit=5)
        self.assertIsInstance(candles, list)  # Should return mock data

        stress_result = calm_state_cache.set_stress_flag(1, True, 'ULTRA')
        self.assertFalse(stress_result)

    def test_mock_data_fallback(self):
        """Test that mock data is generated when Redis data is unavailable"""
        # With no Redis, should generate mock candlesticks
        candles = candlestick_service.generate_candlestick('EURUSD', 'M1', limit=3)

        self.assertIsInstance(candles, list)
        self.assertEqual(len(candles), 3)

        for candle in candles:
            self.assertIn('time', candle)
            self.assertIn('open', candle)
            self.assertIn('high', candle)
            self.assertIn('low', candle)
            self.assertIn('close', candle)
            self.assertIn('volume', candle)