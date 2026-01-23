"""
Market API Serializers
DRF serializers for market endpoints.
"""
from rest_framework import serializers
from market.models import Instrument


class InstrumentSerializer(serializers.ModelSerializer):
    """Instrument serializer"""
    
    class Meta:
        model = Instrument
        fields = ['id', 'symbol', 'is_halal', 'is_crypto', 'min_stop_distance']


class CandlestickSerializer(serializers.Serializer):
    """Single candlestick data serializer"""
    
    time = serializers.DateTimeField(help_text="Candle timestamp (ISO format)")
    open = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Open price"
    )
    high = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="High price"
    )
    low = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Low price"
    )
    close = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Close price"
    )
    volume = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Volume"
    )


class CandlestickResponseSerializer(serializers.Serializer):
    """Candlestick API response serializer"""
    
    symbol = serializers.CharField(help_text="Trading symbol")
    timeframe = serializers.CharField(help_text="Timeframe (M1, M5, H1, D1, etc.)")
    count = serializers.IntegerField(help_text="Number of candles returned")
    candles = CandlestickSerializer(many=True, help_text="List of candlestick data")
