"""
Market Price API - MT5 Style
Provides real-time market prices (bid/ask/mid) for Flutter app.
Supports demo (mock) and real (TwelveData/Binance) price feeds with Redis caching.
"""
import json
import logging
import os
from datetime import datetime
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.permissions import AllowAny

from market.price_feed import get_price_feed
from market.serializers.price import MarketPriceResponseSerializer
from market.serializers import MarketPriceSerializer

logger = logging.getLogger(__name__)

class MarketPriceAPIView(APIView):
    """
    Get current market price (bid/ask/mid) for a symbol - MT5 Style.
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        parameters=[
            {
                "name": "symbol",
                "required": True,
                "in": "query",
                "description": "Trading symbol (e.g., EURUSD, BTCUSD)",
                "schema": {"type": "string"},
            },
            {
                "name": "account",
                "required": False,
                "in": "query",
                "description": "Account type: 'demo' for mock prices, 'real' for real API (default: demo)",
                "schema": {"type": "string", "enum": ["demo", "real"], "default": "demo"},
            },
        ],
        responses={
            200: MarketPriceResponseSerializer,
            400: inline_serializer(
                name="ErrorResponse",
                fields={"error": serializers.CharField()}
            ),
        },
        summary="Get market price",
    )
    def get(self, request):
        symbol = request.query_params.get("symbol", "").upper()
        account = request.query_params.get("account", "demo").lower()
        
        if not symbol:
            return Response({"error": "symbol parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if account not in ["demo", "real"]:
            return Response({"error": "account parameter must be 'demo' or 'real'"}, status=status.HTTP_400_BAD_REQUEST)
        
        return self._get_price(symbol, account)

    @extend_schema(
        request=MarketPriceSerializer,
        responses={
            201: inline_serializer(
                name="PriceSavedResponse",
                fields={"message": serializers.CharField()}
            ),
            400: OpenApiResponse(description="Validation error"),
            500: OpenApiResponse(description="Redis or Server error"),
        },
        summary="Set market price",
    )
    def post(self, request):
        serializer = MarketPriceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        symbol = data['symbol']
        bid = data['bid']
        ask = data['ask']
        mode = data['mode']
        
        mid = (bid + ask) / 2
        price_data = {
            'symbol': symbol,
            'bid': str(bid),
            'ask': str(ask),
            'mid': str(mid),
            'timestamp': datetime.utcnow().isoformat() + "Z",
        }
        
        # Improved Redis Handling for Koyeb
        try:
            import redis
            redis_url = os.getenv('REDIS_URL')
            if redis_url:
                # Use a context manager for the connection if possible, 
                # or ensure the client is reusable.
                redis_client = redis.from_url(redis_url, decode_responses=True)
                key = f"market:{mode}:{symbol}"
                redis_client.set(key, json.dumps(price_data))
                return Response({"message": "Price saved successfully"}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": "REDIS_URL environment variable not set"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Failed to save price to Redis: {e}")
            return Response({"error": "Storage failure"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_price(self, symbol: str, account: str):
        try:
            price_feed = get_price_feed()
            price_data = price_feed.get_bid_ask(symbol, account_type=account)
            
            response_data = {
                "symbol": symbol,
                "bid": str(price_data["bid"]),
                "ask": str(price_data["ask"]),
                "mid": str(price_data["mid"]),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "demo": account == "demo",
            }
            
            serializer = MarketPriceResponseSerializer(data=response_data)
            serializer.is_valid(raise_exception=True)
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Fetch failed for {symbol}: {str(e)}", exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MarketPricesBulkAPIView(APIView):
    """
    Get prices for multiple symbols at once.
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        request=inline_serializer(
            name="BulkPriceRequest",
            fields={
                "symbols": serializers.ListField(child=serializers.CharField()),
                "account": serializers.ChoiceField(choices=["demo", "real"], default="demo")
            }
        ),
        responses={
            200: inline_serializer(
                name="BulkPriceResponse",
                fields={
                    "prices": MarketPriceResponseSerializer(many=True)
                }
            ),
        },
        summary="Get multiple market prices",
    )
    def post(self, request):
        symbols = request.data.get("symbols", [])
        account = request.data.get("account", "demo").lower()
        
        if not symbols or not isinstance(symbols, list):
            return Response({"error": "symbols must be an array"}, status=status.HTTP_400_BAD_REQUEST)
        
        prices = []
        price_feed = get_price_feed()
        
        for symbol in symbols[:50]: # Enforce 50 limit
            try:
                symbol_upper = symbol.upper()
                p = price_feed.get_bid_ask(symbol_upper, account_type=account)
                prices.append({
                    "symbol": symbol_upper,
                    "bid": str(p["bid"]),
                    "ask": str(p["ask"]),
                    "mid": str(p["mid"]),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "demo": account == "demo",
                })
            except:
                continue
        
        return Response({"prices": prices}, status=status.HTTP_200_OK)
