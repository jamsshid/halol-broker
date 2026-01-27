"""
Unified Market Price Feed - MT5 Style
Supports demo (mock) and real (TwelveData/Binance) price feeds with Redis caching.
"""
import json
import logging
import random
import time
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Literal

import requests
from django.conf import settings
from django_redis import get_redis_connection

logger = logging.getLogger(__name__)


class MockPriceFeed:
    """Mock price feed for demo accounts - MT5 style tick simulation"""
    
    BASE_PRICES = {
        # Forex
        "EURUSD": Decimal("1.1000"),
        "GBPUSD": Decimal("1.2700"),
        "USDJPY": Decimal("150.00"),
        "AUDUSD": Decimal("0.6500"),
        "USDCAD": Decimal("1.3500"),
        "USDCHF": Decimal("0.8800"),
        "NZDUSD": Decimal("0.6000"),
        # Crypto
        "BTCUSD": Decimal("45000.00"),
        "ETHUSD": Decimal("2500.00"),
        "USDTUSD": Decimal("1.0000"),
        "USDCUSD": Decimal("1.0000"),
    }
    
    VOLATILITY = Decimal("0.001")  # 0.1% volatility
    
    def __init__(self):
        self._price_cache: Dict[str, Decimal] = {}
        self._last_update: Dict[str, datetime] = {}
    
    def get_price(self, symbol: str) -> Decimal:
        """Get mock price with tick-based movement"""
        symbol_upper = symbol.upper()
        
        # Get previous price or base price
        if symbol_upper in self._price_cache:
            previous_price = self._price_cache[symbol_upper]
        else:
            previous_price = self.BASE_PRICES.get(symbol_upper)
            if previous_price is None:
                previous_price = Decimal("100.00")
                self.BASE_PRICES[symbol_upper] = previous_price
        
        # Tick-based movement: small incremental change
        direction = Decimal("1") if random.random() > 0.5 else Decimal("-1")
        tick_size = self.VOLATILITY * previous_price * Decimal(str(random.uniform(0.1, 1.0)))
        current_price = previous_price + (direction * tick_size)
        
        # Ensure price doesn't go negative
        if current_price <= Decimal("0"):
            current_price = previous_price * Decimal("0.99")
        
        # Update cache
        self._price_cache[symbol_upper] = current_price
        self._last_update[symbol_upper] = datetime.utcnow()
        
        # Self-validation
        assert current_price > 0, f"Mock price must be positive: {current_price}"
        
        return current_price.quantize(Decimal("0.0001"))
    
    def get_bid_ask(self, symbol: str) -> Dict[str, Decimal]:
        """Get bid/ask prices with spread"""
        mid_price = self.get_price(symbol)
        
        # Calculate spread based on symbol type
        if any(c in symbol.upper() for c in ["BTC", "ETH", "USDT", "USDC"]):
            base_spread = Decimal("0.0001")  # 0.01% for crypto
        else:
            base_spread = Decimal("0.0001")  # 1 pip for forex
        
        spread = base_spread * mid_price
        bid = mid_price - (spread / Decimal("2"))
        ask = mid_price + (spread / Decimal("2"))
        
        return {
            "bid": bid.quantize(Decimal("0.0001")),
            "ask": ask.quantize(Decimal("0.0001")),
            "mid": mid_price
        }


class TwelveDataFeed:
    """TwelveData API feed for Forex symbols (real accounts)"""
    
    BASE_URL = "https://api.twelvedata.com"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'TWELVEDATA_API_KEY', None)
    
    def get_price(self, symbol: str) -> Optional[Decimal]:
        """Get real price from TwelveData API"""
        if not self.api_key:
            logger.warning("TwelveData API key not configured")
            return None
        
        try:
            url = f"{self.BASE_URL}/price"
            params = {
                "symbol": symbol,
                "apikey": self.api_key,
                "format": "json"
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if "price" in data:
                price = Decimal(str(data["price"]))
                # Self-validation
                assert price > 0, f"TwelveData price must be positive: {price}"
                logger.info(f"TwelveData price fetched: {symbol}={price}")
                return price.quantize(Decimal("0.0001"))
            else:
                logger.error(f"TwelveData API error: {data}")
                return None
                
        except Exception as e:
            logger.error(f"TwelveData API error for {symbol}: {str(e)}", exc_info=True)
            return None
    
    def get_bid_ask(self, symbol: str) -> Optional[Dict[str, Decimal]]:
        """Get bid/ask from TwelveData (uses quote endpoint)"""
        if not self.api_key:
            return None
        
        try:
            url = f"{self.BASE_URL}/quote"
            params = {
                "symbol": symbol,
                "apikey": self.api_key,
                "format": "json"
            }
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if "bid_price" in data and "ask_price" in data:
                bid = Decimal(str(data["bid_price"]))
                ask = Decimal(str(data["ask_price"]))
                mid = (bid + ask) / Decimal("2")
                
                # Self-validation
                assert bid > 0, f"TwelveData bid must be positive: {bid}"
                assert ask > 0, f"TwelveData ask must be positive: {ask}"
                assert ask > bid, f"TwelveData ask must be greater than bid: {ask} <= {bid}"
                
                logger.info(f"TwelveData bid/ask fetched: {symbol} bid={bid} ask={ask}")
                
                return {
                    "bid": bid.quantize(Decimal("0.0001")),
                    "ask": ask.quantize(Decimal("0.0001")),
                    "mid": mid.quantize(Decimal("0.0001"))
                }
            else:
                # Fallback to price endpoint
                price = self.get_price(symbol)
                if price:
                    spread = price * Decimal("0.0001")
                    return {
                        "bid": (price - spread / Decimal("2")).quantize(Decimal("0.0001")),
                        "ask": (price + spread / Decimal("2")).quantize(Decimal("0.0001")),
                        "mid": price
                    }
                return None
                
        except Exception as e:
            logger.error(f"TwelveData quote API error for {symbol}: {str(e)}", exc_info=True)
            return None


class BinanceFeed:
    """Binance API feed for Crypto symbols (real accounts)"""
    
    BASE_URL = "https://api.binance.com/api/v3"
    
    def get_price(self, symbol: str) -> Optional[Decimal]:
        """Get real price from Binance API"""
        try:
            # Convert symbol format (BTCUSD -> BTCUSDT)
            binance_symbol = symbol.upper()
            if not binance_symbol.endswith("USDT") and not binance_symbol.endswith("USD"):
                # Try to append USDT
                if "USD" in binance_symbol:
                    binance_symbol = binance_symbol.replace("USD", "USDT")
                else:
                    binance_symbol = f"{binance_symbol}USDT"
            
            url = f"{self.BASE_URL}/ticker/price"
            params = {"symbol": binance_symbol}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if "price" in data:
                price = Decimal(str(data["price"]))
                # Self-validation
                assert price > 0, f"Binance price must be positive: {price}"
                logger.info(f"Binance price fetched: {symbol}={price}")
                return price.quantize(Decimal("0.0001"))
            else:
                logger.error(f"Binance API error: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Binance API error for {symbol}: {str(e)}", exc_info=True)
            return None
    
    def get_bid_ask(self, symbol: str) -> Optional[Dict[str, Decimal]]:
        """Get bid/ask from Binance order book"""
        try:
            # Convert symbol format
            binance_symbol = symbol.upper()
            if not binance_symbol.endswith("USDT") and not binance_symbol.endswith("USD"):
                if "USD" in binance_symbol:
                    binance_symbol = binance_symbol.replace("USD", "USDT")
                else:
                    binance_symbol = f"{binance_symbol}USDT"
            
            url = f"{self.BASE_URL}/ticker/bookTicker"
            params = {"symbol": binance_symbol}
            
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if "bidPrice" in data and "askPrice" in data:
                bid = Decimal(str(data["bidPrice"]))
                ask = Decimal(str(data["askPrice"]))
                mid = (bid + ask) / Decimal("2")
                
                # Self-validation
                assert bid > 0, f"Binance bid must be positive: {bid}"
                assert ask > 0, f"Binance ask must be positive: {ask}"
                assert ask > bid, f"Binance ask must be greater than bid: {ask} <= {bid}"
                
                logger.info(f"Binance bid/ask fetched: {symbol} bid={bid} ask={ask}")
                
                return {
                    "bid": bid.quantize(Decimal("0.0001")),
                    "ask": ask.quantize(Decimal("0.0001")),
                    "mid": mid.quantize(Decimal("0.0001"))
                }
            else:
                # Fallback to price endpoint
                price = self.get_price(symbol)
                if price:
                    spread = price * Decimal("0.0001")
                    return {
                        "bid": (price - spread / Decimal("2")).quantize(Decimal("0.0001")),
                        "ask": (price + spread / Decimal("2")).quantize(Decimal("0.0001")),
                        "mid": price
                    }
                return None
                
        except Exception as e:
            logger.error(f"Binance bookTicker API error for {symbol}: {str(e)}", exc_info=True)
            return None


class PriceFeed:
    """
    Unified Price Feed - MT5 Style
    Handles demo (mock) and real (TwelveData/Binance) feeds with Redis caching.
    """
    
    REDIS_TTL = 5  # 5 seconds TTL
    REDIS_KEY_PREFIX = "price"
    
    def __init__(self):
        self.mock_feed = MockPriceFeed()
        self.twelvedata_feed = TwelveDataFeed()
        self.binance_feed = BinanceFeed()
        self._redis_client = None
    
    def _get_redis_client(self):
        """Get Redis client with fallback"""
        if self._redis_client is None:
            try:
                self._redis_client = get_redis_connection("default")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self._redis_client = False  # Mark as unavailable
        return self._redis_client if self._redis_client else None
    
    def _make_redis_key(self, symbol: str) -> str:
        """Create Redis key for price data"""
        return f"{self.REDIS_KEY_PREFIX}:{symbol.upper()}"
    
    def _is_crypto(self, symbol: str) -> bool:
        """Check if symbol is crypto"""
        crypto_keywords = ["BTC", "ETH", "USDT", "USDC", "BNB", "ADA", "SOL", "XRP", "DOT", "DOGE"]
        return any(keyword in symbol.upper() for keyword in crypto_keywords)
    
    def get_price(
        self, 
        symbol: str, 
        account_type: Literal["demo", "real"] = "demo"
    ) -> Decimal:
        """
        Get current price for symbol with Redis caching.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD", "BTCUSD")
            account_type: "demo" for mock prices, "real" for real API
        
        Returns:
            Current price (Decimal)
        
        Raises:
            AssertionError: If price is invalid (<= 0)
        """
        symbol_upper = symbol.upper()
        redis_key = self._make_redis_key(symbol_upper)
        redis_hit = False
        source = "unknown"
        
        # Try Redis cache first
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                cached_data = redis_client.get(redis_key)
                if cached_data:
                    data = json.loads(cached_data)
                    if account_type == data.get("account_type") and "price" in data:
                        price = Decimal(str(data["price"]))
                        # Self-validation
                        assert price > 0, f"Cached price must be positive: {price}"
                        redis_hit = True
                        source = f"redis-{data.get('source', 'unknown')}"
                        logger.info(
                            f"Price cache HIT: {symbol_upper} account={account_type} "
                            f"price={price} source={source}"
                        )
                        return price
            except Exception as e:
                logger.warning(f"Redis read error: {e}")
        
        # Cache miss - fetch from source
        logger.info(f"Price cache MISS: {symbol_upper} account={account_type}")
        
        price = None
        if account_type == "demo":
            price = self.mock_feed.get_price(symbol_upper)
            source = "mock"
        else:  # real
            # Try real API based on symbol type
            if self._is_crypto(symbol_upper):
                price = self.binance_feed.get_price(symbol_upper)
                source = "binance"
            else:
                price = self.twelvedata_feed.get_price(symbol_upper)
                source = "twelvedata"
            
            # Fallback to mock if real API fails
            if price is None:
                logger.warning(
                    f"Real API failed for {symbol_upper}, falling back to mock"
                )
                price = self.mock_feed.get_price(symbol_upper)
                source = "mock-fallback"
        
        # Self-validation
        assert price is not None, f"Price must not be None for {symbol_upper}"
        assert price > 0, f"Price must be positive: {price} for {symbol_upper}"
        
        # Cache in Redis
        if redis_client:
            try:
                cache_data = {
                    "price": str(price),
                    "account_type": account_type,
                    "source": source,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                redis_client.setex(
                    redis_key,
                    self.REDIS_TTL,
                    json.dumps(cache_data)
                )
            except Exception as e:
                logger.warning(f"Redis write error: {e}")
        
        logger.info(
            f"Price fetched: {symbol_upper} account={account_type} "
            f"price={price} source={source} redis_hit={redis_hit}"
        )
        
        return price
    
    def get_bid_ask(
        self, 
        symbol: str, 
        account_type: Literal["demo", "real"] = "demo"
    ) -> Dict[str, Decimal]:
        """
        Get bid/ask prices with Redis caching.
        
        Args:
            symbol: Trading symbol
            account_type: "demo" for mock, "real" for real API
        
        Returns:
            Dict with 'bid', 'ask', 'mid' (all Decimal)
        
        Raises:
            AssertionError: If prices are invalid
        """
        symbol_upper = symbol.upper()
        redis_key = self._make_redis_key(symbol_upper)
        redis_hit = False
        source = "unknown"
        
        # Try Redis cache first
        redis_client = self._get_redis_client()
        if redis_client:
            try:
                cached_data = redis_client.get(redis_key)
                if cached_data:
                    data = json.loads(cached_data)
                    if account_type == data.get("account_type") and "bid" in data and "ask" in data:
                        bid = Decimal(str(data["bid"]))
                        ask = Decimal(str(data["ask"]))
                        mid = Decimal(str(data.get("mid", (bid + ask) / Decimal("2"))))
                        
                        # Self-validation
                        assert bid > 0, f"Cached bid must be positive: {bid}"
                        assert ask > 0, f"Cached ask must be positive: {ask}"
                        assert ask > bid, f"Cached ask must be greater than bid: {ask} <= {bid}"
                        
                        redis_hit = True
                        source = f"redis-{data.get('source', 'unknown')}"
                        logger.info(
                            f"Bid/Ask cache HIT: {symbol_upper} account={account_type} "
                            f"bid={bid} ask={ask} source={source}"
                        )
                        return {"bid": bid, "ask": ask, "mid": mid}
            except Exception as e:
                logger.warning(f"Redis read error: {e}")
        
        # Cache miss - fetch from source
        logger.info(f"Bid/Ask cache MISS: {symbol_upper} account={account_type}")
        
        price_data = None
        if account_type == "demo":
            price_data = self.mock_feed.get_bid_ask(symbol_upper)
            source = "mock"
        else:  # real
            # Try real API based on symbol type
            if self._is_crypto(symbol_upper):
                price_data = self.binance_feed.get_bid_ask(symbol_upper)
                source = "binance"
            else:
                price_data = self.twelvedata_feed.get_bid_ask(symbol_upper)
                source = "twelvedata"
            
            # Fallback to mock if real API fails
            if price_data is None:
                logger.warning(
                    f"Real API failed for {symbol_upper}, falling back to mock"
                )
                price_data = self.mock_feed.get_bid_ask(symbol_upper)
                source = "mock-fallback"
        
        # Self-validation
        assert price_data is not None, f"Price data must not be None for {symbol_upper}"
        assert "bid" in price_data, f"Bid missing in price data for {symbol_upper}"
        assert "ask" in price_data, f"Ask missing in price data for {symbol_upper}"
        bid = price_data["bid"]
        ask = price_data["ask"]
        mid = price_data.get("mid", (bid + ask) / Decimal("2"))
        
        assert bid > 0, f"Bid must be positive: {bid} for {symbol_upper}"
        assert ask > 0, f"Ask must be positive: {ask} for {symbol_upper}"
        assert ask > bid, f"Ask must be greater than bid: {ask} <= {bid} for {symbol_upper}"
        
        # Cache in Redis
        if redis_client:
            try:
                cache_data = {
                    "bid": str(bid),
                    "ask": str(ask),
                    "mid": str(mid),
                    "account_type": account_type,
                    "source": source,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                redis_client.setex(
                    redis_key,
                    self.REDIS_TTL,
                    json.dumps(cache_data)
                )
            except Exception as e:
                logger.warning(f"Redis write error: {e}")
        
        logger.info(
            f"Bid/Ask fetched: {symbol_upper} account={account_type} "
            f"bid={bid} ask={ask} source={source} redis_hit={redis_hit}"
        )
        
        return {"bid": bid, "ask": ask, "mid": mid}


# Global singleton instance
_price_feed_instance: Optional[PriceFeed] = None


def get_price_feed() -> PriceFeed:
    """Get price feed instance (singleton pattern)"""
    global _price_feed_instance
    if _price_feed_instance is None:
        _price_feed_instance = PriceFeed()
    return _price_feed_instance


def reset_price_feed():
    """Reset price feed singleton (useful for testing)"""
    global _price_feed_instance
    _price_feed_instance = None
