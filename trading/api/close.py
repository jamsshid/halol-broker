from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse

from trading.models import Position
from trading.services.trade_close import close_trade
from trading.serializers import (
    TradeCloseRequestSerializer,
    TradeCloseResponseSerializer,
)


class TradeCloseAPIView(APIView):
    """
    Close a trade position (full or partial)
    
    POST /api/trade/close/
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=TradeCloseRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=TradeCloseResponseSerializer,
                description="Trade closed successfully"
            ),
            400: OpenApiResponse(
                description="Bad request - validation error",
                response={
                    "type": "object",
                    "properties": {"error": {"type": "string"}}
                }
            ),
            404: OpenApiResponse(
                description="Position not found",
                response={
                    "type": "object",
                    "properties": {"error": {"type": "string"}}
                }
            ),
        },
        summary="Close a trade position",
        description="Close a trade position (full or partial) with PnL calculation"
    )
    def post(self, request):
        """Close a trade position"""
        # Validate request data
        serializer = TradeCloseRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            position_id = serializer.validated_data.get("position_id")
            closing_price = serializer.validated_data.get("closing_price")
            close_size = serializer.validated_data.get("close_size")
            
            # Get position and verify ownership
            try:
                position = Position.objects.select_related("account").get(id=position_id)
            except Position.DoesNotExist:
                return Response(
                    {"error": "Position not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verify position belongs to user
            if position.account.user != request.user:
                return Response(
                    {"error": "Access denied"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Convert prices
            closing_price = Decimal(str(closing_price))
            if close_size is not None:
                close_size = Decimal(str(close_size))
            
            # Close trade
            closed_position = close_trade(
                position_id=position_id,
                closing_price=closing_price,
                close_size=close_size
            )
            
            # Return response using serializer
            response_data = {
                "position_id": closed_position.id,
                "status": closed_position.status,
                "pnl": closed_position.pnl or Decimal("0.00"),
                "closing_price": closing_price,
                "remaining_size": closed_position.remaining_size or Decimal("0.00"),
            }
            response_serializer = TradeCloseResponseSerializer(data=response_data)
            response_serializer.is_valid()  # Validate response structure
            
            return Response(
                response_serializer.validated_data,
                status=status.HTTP_200_OK
            )
            
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to close trade: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
