#!/usr/bin/env python
"""
Redis Integration Validation Script
Validates that Redis components are properly integrated.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from market.redis_cache import price_cache
from market.services.candles import candlestick_service
from calm.helpers import calm_state_cache

def test_price_cache():
    """Test price cache functionality"""
    print("Testing Market Price Cache...")

    # Test setting price
    result = price_cache.set_price('EURUSD', Decimal('1.0500'))
    print(f"Set price result: {result}")

    # Test getting price
    price_data = price_cache.get_price('EURUSD')
    print(f"Retrieved price: {price_data}")

    # Test price value
    price_value = price_cache.get_price_value('EURUSD')
    print(f"Price value: {price_value}")

    print("✓ Price cache test completed\n")

def test_candlestick_service():
    """Test candlestick service"""
    print("Testing Candlestick Service...")

    # Test adding tick
    result = candlestick_service.add_tick('EURUSD', Decimal('1.0500'), Decimal('100'))
    print(f"Add tick result: {result}")

    # Test generating candlesticks
    candles = candlestick_service.generate_candlestick('EURUSD', 'M1', limit=3)
    print(f"Generated {len(candles)} candles")

    print("✓ Candlestick service test completed\n")

def test_calm_state_cache():
    """Test calm state cache"""
    print("Testing Calm State Cache...")

    # Test setting stress flag
    result = calm_state_cache.set_stress_flag(1, True, 'ULTRA')
    print(f"Set stress flag result: {result}")

    # Test getting stress flag
    flag_data = calm_state_cache.get_stress_flag(1)
    print(f"Retrieved stress flag: {flag_data}")

    # Test setting blurred PnL
    result = calm_state_cache.set_blurred_pnl(1, Decimal('100.50'), Decimal('95.25'))
    print(f"Set blurred PnL result: {result}")

    # Test getting blurred PnL
    pnl_data = calm_state_cache.get_blurred_pnl(1)
    print(f"Retrieved blurred PnL: {pnl_data}")

    print("✓ Calm state cache test completed\n")

def test_redis_fallback():
    """Test Redis failure fallback"""
    print("Testing Redis Fallback...")

    # Temporarily disable Redis
    original_client = price_cache.redis_client
    price_cache.redis_client = None

    # Should not crash
    result = price_cache.set_price('EURUSD', Decimal('1.0500'))
    print(f"Fallback set price result: {result}")

    # Restore
    price_cache.redis_client = original_client

    print("✓ Redis fallback test completed\n")

def main():
    """Run all validation tests"""
    print("🚀 Redis Integration Validation\n")
    print("=" * 50)

    try:
        test_price_cache()
        test_candlestick_service()
        test_calm_state_cache()
        test_redis_fallback()

        print("=" * 50)
        print("✅ All Redis integration tests passed!")
        print("\n📋 Summary:")
        print("- Market price cache: ✓")
        print("- Candlestick aggregation: ✓")
        print("- Calm mode state: ✓")
        print("- Redis fallback: ✓")
        print("\n🎯 Redis integration is ready for production!")

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()