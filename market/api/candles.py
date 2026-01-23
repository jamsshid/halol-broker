"""
Chart Data API - Candlestick Endpoints
Provides OHLC data for frontend charting.
"""
from datetime import datetime
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny  # Public endpoint for chart data

from market.services.candles import candlestick_service
from market.serializers import CandlestickResponseSerializer
from common.enums import Timeframe


class CandlestickAPIView(APIView):
    """
    Get candlestick (OHLC) data for charting
    
    GET /api/market/candles/?symbol=EURUSD&timeframe=H1&limit=100
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
                "name": "timeframe",
                "required": True,
                "in": "query",
                "description": "Timeframe (M1, M5, M15, M30, H1, H4, D1, W1, MN1)",
                "schema": {"type": "string", "enum": Timeframe.all_values()},
            },
            {
                "name": "limit",
                "required": False,
                "in": "query",
                "description": "Number of candles to return (default: 100)",
                "schema": {"type": "integer", "default": 100},
            },
            {
                "name": "start_time",
                "required": False,
                "in": "query",
                "description": "Start time (ISO format)",
                "schema": {"type": "string", "format": "date-time"},
            },
            {
                "name": "end_time",
                "required": False,
                "in": "query",
                "description": "End time (ISO format, defaults to now)",
                "schema": {"type": "string", "format": "date-time"},
            },
        ],
        responses={
            200: OpenApiResponse(
                response=CandlestickResponseSerializer,
                description="Candlestick data retrieved successfully"
            ),
            400: OpenApiResponse(
                description="Bad request - validation error",
                response={
                    "type": "object",
                    "properties": {"error": {"type": "string"}}
                }
            ),
        },
        summary="Get candlestick (OHLC) data",
        description="Get candlestick data for charting. Supports multiple timeframes and caching."
    )
    def get(self, request):
        """Get candlestick data"""
        symbol = request.query_params.get("symbol")
        timeframe = request.query_params.get("timeframe")
        limit = int(request.query_params.get("limit", 100))
        
        if not symbol:
            return Response(
                {"error": "symbol parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not timeframe:
            return Response(
                {"error": "timeframe parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate timeframe
        if timeframe not in Timeframe.all_values():
            return Response(
                {"error": f"Invalid timeframe. Must be one of: {', '.join(Timeframe.all_values())}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse optional time parameters
        start_time = None
        end_time = None
        
        start_time_str = request.query_params.get("start_time")
        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            except ValueError:
                return Response(
                    {"error": "Invalid start_time format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        end_time_str = request.query_params.get("end_time")
        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            except ValueError:
                return Response(
                    {"error": "Invalid end_time format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Generate candlestick data
        try:
            candles = candlestick_service.generate_candlestick(
                symbol=symbol.upper(),
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            
            # Return response using serializer
            response_data = {
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "count": len(candles),
                "candles": candles,
            }
            response_serializer = CandlestickResponseSerializer(data=response_data)
            response_serializer.is_valid()  # Validate response structure
            
            return Response(
                response_serializer.validated_data,
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to generate candlestick data: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
