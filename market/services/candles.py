"""
Candlestick Data Aggregation Service
Generates OHLC (Open, High, Low, Close) data for charting.
Supports Redis caching for performance and real-time tick aggregation.
"""
import json
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict

import redis
from django.conf import settings
from django.core.cache import cache

from common.enums import Timeframe

logger = logging.getLogger(__name__)


# Singleton instance
_candlestick_service_instance = None


class CandlestickService:
    """Candlestick data aggregation service with Redis support"""

    # Redis keys
    TICK_KEY_PREFIX = "tick"
    CANDLE_KEY_PREFIX = "candle"
    CANDLE_TTL = 3600  # 1 hour TTL for candles
    TICK_TTL = 300     # 5 minutes TTL for raw ticks

    def __init__(self):
        self.redis_client = self._get_redis_client()

    def _get_redis_client(self) -> Optional[redis.Redis]:
        """Get Redis client with fallback"""
        try:
            from django_redis import get_redis_connection
            return get_redis_connection("default")
        except Exception as e:
            logger.warning(f"Redis connection failed for candles: {e}")
            return None

    @staticmethod
    def _get_timeframe_seconds(timeframe: str) -> int:
        """Convert timeframe to seconds"""
        timeframe_map = {
            Timeframe.M1: 60,
            Timeframe.M5: 300,
            Timeframe.M15: 900,
            Timeframe.M30: 1800,
            Timeframe.H1: 3600,
            Timeframe.H4: 14400,
            Timeframe.D1: 86400,
            Timeframe.W1: 604800,
            Timeframe.MN1: 2592000,
        }
        return timeframe_map.get(timeframe, 60)

    @staticmethod
    def _round_to_timeframe(timestamp: datetime, timeframe: str) -> datetime:
        """Round timestamp to timeframe boundary"""
        seconds = CandlestickService._get_timeframe_seconds(timeframe)

        if timeframe == Timeframe.D1:
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeframe == Timeframe.H1 or timeframe == Timeframe.H4:
            return timestamp.replace(minute=0, second=0, microsecond=0)
        else:
            # Minutes-based
            minutes = (timestamp.minute // (seconds // 60)) * (seconds // 60)
            return timestamp.replace(minute=minutes, second=0, microsecond=0)

    def _make_tick_key(self, symbol: str) -> str:
        """Create Redis key for raw ticks"""
        return f"{self.TICK_KEY_PREFIX}:{symbol.upper()}"

    def _make_candle_key(self, symbol: str, timeframe: str, period_start: datetime) -> str:
        """Create Redis key for candlestick data"""
        period_str = period_start.strftime("%Y%m%d%H%M%S")
        return f"{self.CANDLE_KEY_PREFIX}:{symbol.upper()}:{timeframe}:{period_str}"

    def add_tick(self, symbol: str, price: Decimal, volume: Decimal = Decimal('0'),
                 timestamp: Optional[datetime] = None) -> bool:
        """
        Add raw tick data to Redis for aggregation.

        Args:
            symbol: Trading symbol
            price: Tick price
            volume: Tick volume
            timestamp: Tick timestamp (defaults to now)

        Returns:
            bool: Success status
        """
        try:
            if not self.redis_client:
                logger.debug("Redis not available, skipping tick storage")
                return False

            timestamp = timestamp or datetime.now()
            tick_data = {
                'price': str(price),
                'volume': str(volume),
                'timestamp': timestamp.isoformat()
            }

            key = self._make_tick_key(symbol)
            # Store as sorted set with timestamp as score
            score = timestamp.timestamp()
            self.redis_client.zadd(key, {json.dumps(tick_data): score})

            # Keep only recent ticks (last 24 hours)
            cutoff = (timestamp - timedelta(hours=24)).timestamp()
            self.redis_client.zremrangebyscore(key, '-inf', cutoff)

            # Set TTL
            self.redis_client.expire(key, self.TICK_TTL)

            logger.debug(f"Added tick for {symbol}: {price}")
            return True

        except Exception as e:
            logger.error(f"Failed to add tick for {symbol}: {e}")
            return False

    def _aggregate_ticks_to_candle(self, symbol: str, timeframe: str,
                                  period_start: datetime, period_end: datetime) -> Optional[Dict[str, Any]]:
        """
        Aggregate raw ticks into a single candlestick for given period.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            period_start: Period start time
            period_end: Period end time

        Returns:
            dict: Candlestick data or None
        """
        try:
            if not self.redis_client:
                return None

            key = self._make_tick_key(symbol)
            start_score = period_start.timestamp()
            end_score = period_end.timestamp()

            # Get ticks for this period
            ticks_data = self.redis_client.zrangebyscore(key, start_score, end_score, withscores=True)

            if not ticks_data:
                return None

            # Parse ticks
            prices = []
            volumes = []

            for tick_json, _ in ticks_data:
                try:
                    tick = json.loads(tick_json)
                    prices.append(Decimal(tick['price']))
                    volumes.append(Decimal(tick['volume']))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

            if not prices:
                return None

            # Calculate OHLC
            open_price = prices[0]
            high_price = max(prices)
            low_price = min(prices)
            close_price = prices[-1]
            total_volume = sum(volumes)

            return {
                "time": period_start.isoformat(),
                "open": float(open_price),
                "high": float(high_price),
                "low": float(low_price),
                "close": float(close_price),
                "volume": float(total_volume),
            }

        except Exception as e:
            logger.error(f"Failed to aggregate ticks for {symbol} {timeframe}: {e}")
            return None

    def generate_candlestick(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Generate candlestick data for symbol and timeframe.
        Uses Redis for real-time data, falls back to mock data.

        Args:
            symbol: Trading symbol (e.g., EURUSD, BTCUSD)
            timeframe: Timeframe (M1, M5, H1, D1, etc.)
            start_time: Start time (optional)
            end_time: End time (optional, defaults to now)
            limit: Number of candles to return

        Returns:
            List of candlestick dictionaries
        """
        try:
            end_time = end_time or datetime.now()
            start_time = start_time or (end_time - timedelta(seconds=self._get_timeframe_seconds(timeframe) * limit))

            candles = []

            # Try Redis-based aggregation first
            if self.redis_client:
                current_time = self._round_to_timeframe(start_time, timeframe)
                timeframe_seconds = self._get_timeframe_seconds(timeframe)

                while current_time <= end_time and len(candles) < limit:
                    period_end = current_time + timedelta(seconds=timeframe_seconds)

                    # Check if we have cached candle
                    candle_key = self._make_candle_key(symbol, timeframe, current_time)
                    cached_candle = self.redis_client.get(candle_key)

                    if cached_candle:
                        try:
                            candle = json.loads(cached_candle)
                            candles.append(candle)
                        except json.JSONDecodeError:
                            pass
                    else:
                        # Aggregate from ticks
                        candle = self._aggregate_ticks_to_candle(symbol, timeframe, current_time, period_end)
                        if candle:
                            # Cache the candle
                            self.redis_client.setex(candle_key, self.CANDLE_TTL, json.dumps(candle))
                            candles.append(candle)

                    current_time = period_end

            # If we don't have enough candles from Redis, generate mock data
            if len(candles) < limit:
                mock_candles = self._generate_mock_candles(symbol, timeframe, start_time, end_time, limit - len(candles))
                candles.extend(mock_candles)

            # Sort by time and limit
            candles.sort(key=lambda x: x['time'])
            return candles[-limit:] if len(candles) > limit else candles

        except Exception as e:
            logger.error(f"Failed to generate candlesticks for {symbol} {timeframe}: {e}")
            # Fallback to mock data
            return self._generate_mock_candles(symbol, timeframe, start_time, end_time, limit)

    def _generate_mock_candles(self, symbol: str, timeframe: str,
                              start_time: datetime, end_time: datetime, count: int) -> List[Dict[str, Any]]:
        """Generate mock candlestick data as fallback"""
        try:
            from market.price_feed import get_price_feed
            price_feed = get_price_feed()
            # Use demo account type for mock candles
            base_price = float(price_feed.get_price(symbol, account_type="demo") or 1.0)

            candles = []
            current_time = self._round_to_timeframe(start_time, timeframe)
            timeframe_seconds = self._get_timeframe_seconds(timeframe)

            import random
            for _ in range(count):
                if current_time > end_time:
                    break

                variation = random.uniform(-0.002, 0.002)  # ±0.2%
                open_price = base_price * (1 + random.uniform(-0.001, 0.001))
                high_price = open_price * (1 + abs(variation))
                low_price = open_price * (1 - abs(variation))
                close_price = open_price * (1 + variation)
                volume = random.uniform(100, 1000)

                candle = {
                    "time": current_time.isoformat(),
                    "open": round(open_price, 6),
                    "high": round(high_price, 6),
                    "low": round(low_price, 6),
                    "close": round(close_price, 6),
                    "volume": round(volume, 2),
                }

                candles.append(candle)
                current_time += timedelta(seconds=timeframe_seconds)
                base_price = close_price

            return candles

        except Exception as e:
            logger.error(f"Failed to generate mock candles: {e}")
            return []

    def get_latest_candle(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        """Get latest candlestick for symbol"""
        candles = self.generate_candlestick(
            symbol=symbol,
            timeframe=timeframe,
            limit=1
        )
        return candles[0] if candles else None

    def clear_cache(self, symbol: Optional[str] = None, timeframe: Optional[str] = None):
        """Clear candlestick cache"""
        try:
            if not self.redis_client:
                return

            if symbol and timeframe:
                # Clear specific symbol/timeframe
                pattern = f"{self.CANDLE_KEY_PREFIX}:{symbol.upper()}:{timeframe}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            else:
                # Clear all candle cache
                pattern = f"{self.CANDLE_KEY_PREFIX}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)

        except Exception as e:
            logger.error(f"Failed to clear candle cache: {e}")


# Global instance
candlestick_service = CandlestickService()
