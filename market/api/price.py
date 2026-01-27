"""
Market Price API - MT5 Style
Provides real-time market prices (bid/ask/mid) for Flutter app.
Supports demo (mock) and real (TwelveData/Binance) price feeds with Redis caching.
"""
import logging
from decimal import Decimal
from datetime import datetime
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from market.price_feed import get_price_feed
from market.serializers.price import MarketPriceResponseSerializer

logger = logging.getLogger(__name__)


class MarketPriceAPIView(APIView):
    """
    Get current market price (bid/ask/mid) for a symbol - MT5 Style.
    
    GET /api/market/price?symbol=EURUSD&account=demo
    GET /api/market/price?symbol=EURUSD&account=real
    """
    permission_classes = [AllowAny]  # Public endpoint
    
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
        request={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "account": {"type": "string", "enum": ["demo", "real"]},
            }
        },
        responses={
            200: OpenApiResponse(
                response=MarketPriceResponseSerializer,
                description="Market price retrieved successfully"
            ),
            400: OpenApiResponse(
                description="Bad request - validation error",
                response={
                    "type": "object",
                    "properties": {"error": {"type": "string"}}
                }
            ),
        },
        summary="Get market price",
        description="Get current bid/ask/mid price for a trading symbol. Supports demo (mock) and real (TwelveData/Binance) feeds with Redis caching."
    )
    def get(self, request):
        """GET method - get price from query params"""
        symbol = request.query_params.get("symbol", "").upper()
        account = request.query_params.get("account", "demo").lower()
        
        if not symbol:
            return Response(
                {"error": "symbol parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if account not in ["demo", "real"]:
            return Response(
                {"error": "account parameter must be 'demo' or 'real'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return self._get_price(symbol, account)
    
    def post(self, request):
        """POST method - get price from JSON body"""
        symbol = request.data.get("symbol", "").upper()
        account = request.data.get("account", "demo").lower()
        
        if not symbol:
            return Response(
                {"error": "symbol field is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if account not in ["demo", "real"]:
            return Response(
                {"error": "account field must be 'demo' or 'real'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return self._get_price(symbol, account)
    
    def _get_price(self, symbol: str, account: str):
        """
        Get market price for symbol using unified PriceFeed.
        
        Args:
            symbol: Trading symbol
            account: "demo" for mock prices, "real" for real API
        
        Returns:
            Response with price data (Flutter-ready JSON)
        """
        try:
            # Get unified price feed
            price_feed = get_price_feed()
            
            # Get bid/ask/mid prices with Redis caching
            price_data = price_feed.get_bid_ask(symbol, account_type=account)
            
            # Prepare Flutter-ready response
            response_data = {
                "symbol": symbol,
                "bid": str(price_data["bid"]),
                "ask": str(price_data["ask"]),
                "mid": str(price_data["mid"]),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "demo": account == "demo",
            }
            
            # Log price fetch
            logger.info(
                f"Market price API: symbol={symbol}, account={account}, "
                f"bid={price_data['bid']}, ask={price_data['ask']}",
                extra={
                    "symbol": symbol,
                    "account": account,
                    "bid": str(price_data["bid"]),
                    "ask": str(price_data["ask"]),
                }
            )
            
            # Validate response structure
            serializer = MarketPriceResponseSerializer(data=response_data)
            serializer.is_valid(raise_exception=True)
            
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
            
        except AssertionError as e:
            logger.error(
                f"Price validation failed for {symbol}: {str(e)}",
                extra={"symbol": symbol, "account": account},
                exc_info=True
            )
            return Response(
                {"error": f"Price validation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(
                f"Failed to fetch market price for {symbol}: {str(e)}",
                extra={"symbol": symbol, "account": account},
                exc_info=True
            )
            return Response(
                {"error": f"Failed to fetch market price: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MarketPricesBulkAPIView(APIView):
    """
    Get prices for multiple symbols at once - MT5 Style.
    
    POST /api/market/prices/
    {
        "symbols": ["EURUSD", "BTCUSD", "GBPUSD"],
        "account": "demo"
    }
    """
    permission_classes = [AllowAny]
    
    @extend_schema(
        request={
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of trading symbols"
                },
                "account": {
                    "type": "string",
                    "enum": ["demo", "real"],
                    "default": "demo",
                    "description": "Account type: 'demo' or 'real'"
                },
            },
            "required": ["symbols"]
        },
        responses={
            200: OpenApiResponse(
                description="Market prices retrieved successfully",
                response={
                    "type": "object",
                    "properties": {
                        "prices": {
                            "type": "array",
                            "items": MarketPriceResponseSerializer
                        }
                    }
                }
            ),
        },
        summary="Get multiple market prices",
        description="Get prices for multiple symbols in a single request with Redis caching"
    )
    def post(self, request):
        """Get prices for multiple symbols"""
        symbols = request.data.get("symbols", [])
        account = request.data.get("account", "demo").lower()
        
        if not symbols or not isinstance(symbols, list):
            return Response(
                {"error": "symbols field must be a non-empty array"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if account not in ["demo", "real"]:
            return Response(
                {"error": "account field must be 'demo' or 'real'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Limit to 50 symbols per request
        if len(symbols) > 50:
            return Response(
                {"error": "Maximum 50 symbols per request"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        prices = []
        price_feed = get_price_feed()
        
        for symbol in symbols:
            try:
                symbol_upper = symbol.upper()
                price_data = price_feed.get_bid_ask(symbol_upper, account_type=account)
                
                prices.append({
                    "symbol": symbol_upper,
                    "bid": str(price_data["bid"]),
                    "ask": str(price_data["ask"]),
                    "mid": str(price_data["mid"]),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "demo": account == "demo",
                })
            except Exception as e:
                logger.warning(f"Failed to fetch price for {symbol}: {str(e)}")
                continue
        
        logger.info(
            f"Bulk price fetch: {len(prices)}/{len(symbols)} symbols, account={account}",
            extra={"symbols_count": len(symbols), "prices_count": len(prices), "account": account}
        )
        
        return Response({"prices": prices}, status=status.HTTP_200_OK)
