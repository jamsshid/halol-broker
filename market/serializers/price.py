"""
Market Price Serializers
Serializers for market price API responses.
"""
from rest_framework import serializers


class MarketPriceResponseSerializer(serializers.Serializer):
    """Market price response serializer"""
    
    symbol = serializers.CharField(help_text="Trading symbol (e.g., EURUSD, BTCUSD)")
    bid = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Bid price"
    )
    ask = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Ask price"
    )
    mid = serializers.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Mid price (average of bid and ask)"
    )
    timestamp = serializers.DateTimeField(help_text="Price timestamp (ISO format)")
    demo = serializers.BooleanField(help_text="Whether this is demo (mock) or real price")
