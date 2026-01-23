"""
Market Price Cache - Redis Integration
Fast price caching for real-time trading data.
"""
import json
import logging
from typing import Optional, Dict, Any
from decimal import Decimal

import redis
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class MarketPriceCache:
    """
    Redis-based market price cache for fast price lookups.
    Used for SL/TP monitoring and real-time price feeds.
    """

    PRICE_TTL = 10  # 10 seconds TTL for price data
    PRICE_KEY_PREFIX = "price"

    def __init__(self):
        self.redis_client = self._get_redis_client()

    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client with fallback to Django cache"""
        try:
            # Try to get Redis client from Django cache backend
            from django_redis import get_redis_connection
            return get_redis_connection("default")
        except Exception as e:
            logger.warning(f"Redis connection failed, using fallback: {e}")
            # Fallback to Django cache (which might be locmem in tests)
            return None

    def _make_price_key(self, symbol: str) -> str:
        """Create Redis key for price data"""
        return f"{self.PRICE_KEY_PREFIX}:{symbol.upper()}"

    def set_price(self, symbol: str, price: Decimal, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set current market price for a symbol.

        Args:
            symbol: Trading symbol (e.g., 'EURUSD', 'BTCUSD')
            price: Current market price
            metadata: Additional price metadata (timestamp, volume, etc.)

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            key = self._make_price_key(symbol)
            data = {
                'price': str(price),
                'timestamp': metadata.get('timestamp') if metadata else None,
                'volume': str(metadata.get('volume', 0)) if metadata else '0',
                'bid': str(metadata.get('bid', price)) if metadata else str(price),
                'ask': str(metadata.get('ask', price)) if metadata else str(price),
            }

            if self.redis_client:
                self.redis_client.setex(key, self.PRICE_TTL, json.dumps(data))
            else:
                # Fallback to Django cache
                cache.set(key, data, self.PRICE_TTL)

            logger.debug(f"Set price for {symbol}: {price}")
            return True

        except Exception as e:
            logger.error(f"Failed to set price for {symbol}: {e}")
            return False

    def get_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current market price for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            dict: Price data or None if not found
        """
        try:
            key = self._make_price_key(symbol)

            if self.redis_client:
                data = self.redis_client.get(key)
            else:
                data = cache.get(key)

            if data:
                if isinstance(data, str):
                    return json.loads(data)
                return data

            return None

        except Exception as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None

    def get_price_value(self, symbol: str) -> Optional[Decimal]:
        """
        Get just the price value for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Decimal: Price value or None
        """
        price_data = self.get_price(symbol)
        if price_data and 'price' in price_data:
            try:
                return Decimal(price_data['price'])
            except (ValueError, TypeError):
                return None
        return None

    def delete_price(self, symbol: str) -> bool:
        """
        Delete price data for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            key = self._make_price_key(symbol)

            if self.redis_client:
                return bool(self.redis_client.delete(key))
            else:
                cache.delete(key)
                return True

        except Exception as e:
            logger.error(f"Failed to delete price for {symbol}: {e}")
            return False

    def get_all_prices(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all cached prices (for debugging/admin purposes).

        Returns:
            dict: All price data
        """
        try:
            prices = {}

            if self.redis_client:
                # Get all price keys
                keys = self.redis_client.keys(f"{self.PRICE_KEY_PREFIX}:*")
                for key in keys:
                    data = self.redis_client.get(key)
                    if data:
                        symbol = key.decode().split(':', 1)[1] if isinstance(key, bytes) else key.split(':', 1)[1]
                        prices[symbol] = json.loads(data) if isinstance(data, str) else data
            else:
                # Fallback - we can't easily get all keys from Django cache
                logger.warning("Cannot get all prices from Django cache fallback")
                return {}

            return prices

        except Exception as e:
            logger.error(f"Failed to get all prices: {e}")
            return {}


# Global instance
price_cache = MarketPriceCache()


def set_market_price(symbol: str, price: Decimal, **metadata) -> bool:
    """Convenience function to set market price"""
    return price_cache.set_price(symbol, price, metadata)


def get_market_price(symbol: str) -> Optional[Decimal]:
    """Convenience function to get market price"""
    return price_cache.get_price_value(symbol)