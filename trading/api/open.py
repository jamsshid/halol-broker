from decimal import Decimal
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from trading.models import TradeAccount, Instrument, Position
from trading.services.trade_open import open_trade
from trading.serializers import (
    TradeOpenRequestSerializer,
    TradeOpenResponseSerializer,
)


class TradeOpenAPIView(APIView):
    """
    Open a new trade position
    
    POST /api/trade/open/
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=TradeOpenRequestSerializer,
        responses={
            201: OpenApiResponse(
                response=TradeOpenResponseSerializer,
                description="Trade opened successfully"
            ),
            400: OpenApiResponse(
                description="Bad request - validation error",
                response={
                    "type": "object",
                    "properties": {"error": {"type": "string"}}
                }
            ),
            404: OpenApiResponse(
                description="Account not found",
                response={
                    "type": "object",
                    "properties": {"error": {"type": "string"}}
                }
            ),
        },
        summary="Open a new trade position",
        description="Open a new trading position with validation and risk management"
    )
    def post(self, request):
        """Open a new trade position"""
        # Validate request data
        serializer = TradeOpenRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get account
            account_id = serializer.validated_data.get("account_id")
            
            try:
                account = TradeAccount.objects.get(id=account_id, user=request.user)
            except TradeAccount.DoesNotExist:
                return Response(
                    {"error": "Account not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get validated data
            symbol = serializer.validated_data.get("symbol").upper()
            side = serializer.validated_data.get("side")
            mode = serializer.validated_data.get("mode")
            entry_price = Decimal(str(serializer.validated_data.get("entry_price")))
            stop_loss = Decimal(str(serializer.validated_data.get("stop_loss")))
            take_profit = serializer.validated_data.get("take_profit")
            risk_percent = float(serializer.validated_data.get("risk_percent"))
            timeframe = serializer.validated_data.get("timeframe")
            
            # Get or create instrument
            instrument, created = Instrument.objects.get_or_create(
                symbol=symbol,
                defaults={
                    "is_halal": True,
                    "is_crypto": any(c in symbol for c in ["BTC", "ETH", "USDT", "USDC"]),
                }
            )
            
            # Convert take_profit if provided
            if take_profit is not None:
                take_profit = Decimal(str(take_profit))
            
            # Open trade
            position = open_trade(
                account=account,
                instrument=instrument,
                side=side,
                mode=mode,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_percent=risk_percent,
                timeframe=timeframe
            )
            
            # Return response using serializer
            response_data = {
                "position_id": position.id,
                "symbol": position.instrument.symbol,
                "side": position.side,
                "mode": position.mode,
                "entry_price": position.entry_price,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "position_size": position.position_size,
                "status": position.status,
                "timeframe": position.timeframe,
            }
            response_serializer = TradeOpenResponseSerializer(data=response_data)
            response_serializer.is_valid()  # Validate response structure
            
            return Response(
                response_serializer.validated_data,
                status=status.HTTP_201_CREATED
            )
            
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to open trade: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
