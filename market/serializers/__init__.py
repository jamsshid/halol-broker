"""
Market API Serializers
DRF serializers for market endpoints.
"""
from rest_framework import serializers
from .price import MarketPriceResponseSerializer
from .candles import CandlestickSerializer, CandlestickResponseSerializer


class MarketPriceSerializer(serializers.Serializer):
    """Market price input serializer for POST API"""
    
    symbol = serializers.CharField(required=True, help_text="Trading symbol (e.g., EURUSD)")
    bid = serializers.DecimalField(max_digits=20, decimal_places=6, required=True, help_text="Bid price")
    ask = serializers.DecimalField(max_digits=20, decimal_places=6, required=True, help_text="Ask price")
    mode = serializers.ChoiceField(choices=['demo', 'real'], default='demo', help_text="Account mode")
    source = serializers.CharField(required=False, allow_blank=True, help_text="Price source (optional)")
    
    def validate_symbol(self, value):
        """Validate symbol is uppercase"""
        if value != value.upper():
            raise serializers.ValidationError("Symbol must be uppercase")
        return value
    
    def validate(self, data):
        """Validate bid < ask"""
        if data['bid'] >= data['ask']:
            raise serializers.ValidationError("Bid price must be less than ask price")
        return data


__all__ = [
    "MarketPriceResponseSerializer",
    "CandlestickSerializer",
    "CandlestickResponseSerializer",
    "MarketPriceSerializer",
]
