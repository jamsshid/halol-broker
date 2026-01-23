"""
Market price feed with MOCK support for testing.
Can be switched to real API without changing trade logic.
Enhanced with simulation features: tick-based movement, volatility, delay.
"""
from decimal import Decimal
import random
import time
from typing import Optional, Dict, List
from datetime import datetime, timedelta


class MockPriceFeed:
    """
    Mock price feed for Forex and Crypto.
    Works independently from real API - can be swapped easily.
    Enhanced with simulation features for realistic testing.
    """
    
    # Base prices for mock
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
    
    # Volatility levels by mode
    VOLATILITY = {
        "ULTRA": Decimal("0.0005"),  # Low volatility (0.05%)
        "SEMI": Decimal("0.0015"),   # Medium volatility (0.15%)
        "DEFAULT": Decimal("0.001"),  # Default volatility (0.1%)
    }
    
    def __init__(self, use_mock: bool = True, enable_delay: bool = True, mode: str = "DEFAULT"):
        """
        Args:
            use_mock: If True, use mock prices. If False, connect to real API.
            enable_delay: If True, simulate network delay (50-500ms)
            mode: Mode for volatility ("ULTRA", "SEMI", "DEFAULT")
        """
        self.use_mock = use_mock
        self.enable_delay = enable_delay
        self.mode = mode.upper() if mode else "DEFAULT"
        self._price_cache: Dict[str, Decimal] = {}
        self._last_update: Dict[str, datetime] = {}
        self._price_history: Dict[str, List[Decimal]] = {}  # Track price movement
        self._tick_count: Dict[str, int] = {}  # Track tick count per symbol
    
    def get_price(self, symbol: str) -> Decimal:
        """
        Get current price for symbol with optional delay simulation.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD", "BTCUSD")
        
        Returns:
            Current price (Decimal)
        """
        # Simulate network delay (50-500ms)
        if self.enable_delay:
            delay_ms = random.uniform(50, 500) / 1000.0
            time.sleep(delay_ms)
        
        if self.use_mock:
            return self._get_mock_price(symbol)
        else:
            return self._get_real_price(symbol)
    
    def _get_mock_price(self, symbol: str) -> Decimal:
        """
        Generate mock price with tick-based movement and volatility.
        Price moves incrementally from previous value (if exists).
        """
        symbol_upper = symbol.upper()
        
        # Get volatility based on mode
        volatility = self.VOLATILITY.get(self.mode, self.VOLATILITY["DEFAULT"])
        
        # Get previous price or base price
        if symbol_upper in self._price_cache:
            previous_price = self._price_cache[symbol_upper]
        else:
            previous_price = self.BASE_PRICES.get(symbol_upper)
            if previous_price is None:
                previous_price = Decimal("100.00")
                self.BASE_PRICES[symbol_upper] = previous_price
        
        # Tick-based movement: small incremental change from previous price
        # Direction can be up or down based on random walk
        direction = Decimal("1") if random.random() > 0.5 else Decimal("-1")
        tick_size = volatility * previous_price * Decimal(str(random.uniform(0.1, 1.0)))
        current_price = previous_price + (direction * tick_size)
        
        # Ensure price doesn't go negative or too extreme
        if current_price <= Decimal("0"):
            current_price = previous_price * Decimal("0.99")  # Small downward correction
        
        # Update cache and history
        self._price_cache[symbol_upper] = current_price
        self._last_update[symbol_upper] = datetime.now()
        
        # Track price history (keep last 100 ticks)
        if symbol_upper not in self._price_history:
            self._price_history[symbol_upper] = []
        self._price_history[symbol_upper].append(current_price)
        if len(self._price_history[symbol_upper]) > 100:
            self._price_history[symbol_upper].pop(0)
        
        # Track tick count
        self._tick_count[symbol_upper] = self._tick_count.get(symbol_upper, 0) + 1
        
        return current_price.quantize(Decimal("0.0001"))
    
    def _get_real_price(self, symbol: str) -> Decimal:
        """
        Get real price from API (placeholder - implement with real API).
        This method can be swapped without changing trade logic.
        """
        # TODO: Implement real API call
        # For now, fallback to mock
        return self._get_mock_price(symbol)
    
    def get_bid_ask(self, symbol: str, spread: Optional[Decimal] = None) -> Dict[str, Decimal]:
        """
        Get bid and ask prices with time-varying spread.
        
        Args:
            symbol: Trading symbol
            spread: Optional spread (default: varies by time and symbol type)
        
        Returns:
            Dict with 'bid' and 'ask' prices
        """
        mid_price = self.get_price(symbol)
        
        # Time-varying spread (wider during volatile hours, narrower during calm)
        if spread is None:
            hour = datetime.now().hour
            # Wider spread during market open (8-10 AM, 2-4 PM UTC)
            spread_multiplier = Decimal("1.5") if hour in [8, 9, 14, 15] else Decimal("1.0")
            
            if any(c in symbol.upper() for c in ["BTC", "ETH", "USDT", "USDC"]):
                base_spread = Decimal("0.0001")  # 0.01% for crypto
            else:
                base_spread = Decimal("0.0001")  # 1 pip for forex
            
            spread = base_spread * spread_multiplier
        
        bid = mid_price - (mid_price * spread / Decimal("2"))
        ask = mid_price + (mid_price * spread / Decimal("2"))
        
        return {
            "bid": bid.quantize(Decimal("0.0001")),
            "ask": ask.quantize(Decimal("0.0001")),
            "mid": mid_price
        }
    
    def simulate_tick(self, symbol: str) -> Decimal:
        """
        Simulate a single price tick (incremental price movement).
        Similar to MT5 tick behavior.
        
        Args:
            symbol: Trading symbol
        
        Returns:
            New price after tick
        """
        return self.get_price(symbol)
    
    def simulate_candle(self, symbol: str, timeframe: str = "M1") -> Dict[str, Decimal]:
        """
        Simulate a candlestick (OHLC) for given timeframe.
        Generates multiple ticks and aggregates into OHLC.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe (M1, M5, H1, D1)
        
        Returns:
            Dict with 'open', 'high', 'low', 'close', 'volume'
        """
        # Number of ticks per candle (approximate)
        ticks_per_candle = {
            "M1": 1,
            "M5": 5,
            "M15": 15,
            "M30": 30,
            "H1": 60,
            "H4": 240,
            "D1": 1440,
        }.get(timeframe.upper(), 1)
        
        prices = []
        for _ in range(ticks_per_candle):
            price = self.simulate_tick(symbol)
            prices.append(price)
        
        if not prices:
            price = self.get_price(symbol)
            prices = [price]
        
        open_price = prices[0]
        close_price = prices[-1]
        high_price = max(prices)
        low_price = min(prices)
        volume = Decimal(str(len(prices)))  # Mock volume
        
        return {
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
        }
    
    def set_mode(self, mode: str):
        """
        Set volatility mode (ULTRA, SEMI, DEFAULT).
        
        Args:
            mode: Mode string ("ULTRA", "SEMI", "DEFAULT")
        """
        self.mode = mode.upper() if mode else "DEFAULT"
    
    def get_price_history(self, symbol: str, limit: int = 10) -> List[Decimal]:
        """
        Get recent price history for symbol.
        
        Args:
            symbol: Trading symbol
            limit: Number of recent prices to return
        
        Returns:
            List of recent prices (most recent last)
        """
        symbol_upper = symbol.upper()
        history = self._price_history.get(symbol_upper, [])
        return history[-limit:] if history else []


# Global instance (can be configured via settings)
_price_feed_instance: Optional[MockPriceFeed] = None


def get_price_feed(use_mock: bool = True) -> MockPriceFeed:
    """Get price feed instance (singleton pattern)"""
    global _price_feed_instance
    if _price_feed_instance is None:
        _price_feed_instance = MockPriceFeed(use_mock=use_mock)
    return _price_feed_instance


def reset_price_feed():
    """Reset price feed singleton (useful for testing)"""
    global _price_feed_instance
    _price_feed_instance = None


def get_price(symbol: str) -> Decimal:
    """Convenience function to get price"""
    return get_price_feed().get_price(symbol)


def get_bid_ask(symbol: str) -> Dict[str, Decimal]:
    """Convenience function to get bid/ask"""
    return get_price_feed().get_bid_ask(symbol)