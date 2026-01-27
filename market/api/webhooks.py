"""
Flutter Push Webhooks
Webhook endpoints for Flutter app to receive market price updates and trade events.
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
from trading.hooks import on_pnl_update
from trading.models import Position
from common.hooks import notify

logger = logging.getLogger(__name__)


class FlutterPriceWebhookView(APIView):
    """
    Webhook endpoint for Flutter app to receive market price updates.
    This endpoint can be called periodically by Flutter app or triggered by server events.
    
    POST /api/market/webhooks/price/
    {
        "symbol": "BTCUSD",
        "demo": false
    }
    """
    permission_classes = [AllowAny]  # Public endpoint (can be secured with API key)
    
    @extend_schema(
        request={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "account": {"type": "string", "enum": ["demo", "real"], "default": "demo"},
            },
            "required": ["symbol"]
        },
        responses={
            200: OpenApiResponse(
                description="Price update sent successfully",
                response={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "bid": {"type": "string"},
                                "ask": {"type": "string"},
                                "mid": {"type": "string"},
                                "timestamp": {"type": "string"},
                                "demo": {"type": "boolean"},
                            }
                        }
                    }
                }
            ),
        },
        summary="Flutter price webhook",
        description="Get market price update for Flutter app (webhook format)"
    )
    def post(self, request):
        """Handle Flutter price webhook request"""
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
        
        try:
            # Get unified price feed
            price_feed = get_price_feed()
            
            # Get bid/ask/mid with Redis caching
            price_data = price_feed.get_bid_ask(symbol, account_type=account)
            
            # Prepare Flutter-friendly payload
            payload = {
                "symbol": symbol,
                "bid": str(price_data["bid"]),
                "ask": str(price_data["ask"]),
                "mid": str(price_data["mid"]),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "demo": account == "demo",
            }
            
            # Log webhook call
            logger.info(
                f"Flutter price webhook: symbol={symbol}, account={account}",
                extra={"symbol": symbol, "account": account, "bid": str(price_data["bid"]), "ask": str(price_data["ask"])}
            )
            
            # Send notification (can be extended to push to Flutter via FCM/WebSocket)
            notify(
                event_type="MARKET_PRICE_UPDATE",
                payload=payload,
                user_id=None  # Broadcast to all Flutter clients
            )
            
            return Response({
                "success": True,
                "data": payload
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Flutter price webhook error: {str(e)}",
                extra={"symbol": symbol, "account": account},
                exc_info=True
            )
            return Response(
                {"error": f"Failed to process webhook: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FlutterTradeEventWebhookView(APIView):
    """
    Webhook endpoint for Flutter app to receive trade event notifications.
    Trade events: open, close, SL hit, TP hit, PnL update.
    
    POST /api/market/webhooks/trade-event/
    {
        "position_id": 123,
        "event_type": "TRADE_OPENED"
    }
    """
    permission_classes = [AllowAny]  # Can be secured with API key
    
    @extend_schema(
        request={
            "type": "object",
            "properties": {
                "position_id": {"type": "integer"},
                "event_type": {
                    "type": "string",
                    "enum": ["TRADE_OPENED", "TRADE_CLOSED", "SL_HIT", "TP_HIT", "PNL_UPDATE"]
                },
            },
            "required": ["position_id", "event_type"]
        },
        responses={
            200: OpenApiResponse(
                description="Trade event notification sent",
                response={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "message": {"type": "string"}
                    }
                }
            ),
        },
        summary="Flutter trade event webhook",
        description="Send trade event notification to Flutter app"
    )
    def post(self, request):
        """Handle Flutter trade event webhook"""
        position_id = request.data.get("position_id")
        event_type = request.data.get("event_type")
        
        if not position_id or not event_type:
            return Response(
                {"error": "position_id and event_type are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get position
            try:
                position = Position.objects.select_related("account", "instrument").get(id=position_id)
            except Position.DoesNotExist:
                return Response(
                    {"error": f"Position {position_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Prepare event payload
            payload = {
                "position_id": str(position.id),
                "account_id": str(position.account.id),
                "user_id": position.account.user.id if position.account.user else None,
                "symbol": position.instrument.symbol,
                "side": position.side,
                "mode": position.mode,
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            
            # Add event-specific data
            if event_type in ["TRADE_CLOSED", "SL_HIT", "TP_HIT"]:
                payload["pnl"] = str(position.pnl or "0.00")
            
            if event_type == "PNL_UPDATE":
                payload["unrealized_pnl"] = str(position.unrealized_pnl or "0.00")
            
            # Log webhook call
            logger.info(
                f"Flutter trade event webhook: position_id={position_id}, event_type={event_type}",
                extra={"position_id": position_id, "event_type": event_type, "symbol": position.instrument.symbol}
            )
            
            # Send notification (can be extended to push to Flutter via FCM/WebSocket)
            notify(
                event_type=event_type,
                payload=payload,
                user_id=position.account.user.id if position.account.user else None
            )
            
            return Response({
                "success": True,
                "message": f"Trade event {event_type} notification sent",
                "data": payload
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                f"Flutter trade event webhook error: {str(e)}",
                extra={"position_id": position_id, "event_type": event_type},
                exc_info=True
            )
            return Response(
                {"error": f"Failed to process webhook: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
