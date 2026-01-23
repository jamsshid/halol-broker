"""
Trade History API
Returns trade history for Flutter app.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.utils import timezone
from datetime import timedelta

from trading.models import Position, PositionLog
from trading.serializers import PositionSerializer, PositionLogSerializer


class TradeHistoryAPIView(APIView):
    """
    Get trade history for authenticated user
    
    GET /api/trade/history/?account_id=123&status=OPEN&limit=50
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            {
                "name": "account_id",
                "required": False,
                "in": "query",
                "description": "Filter by account ID",
                "schema": {"type": "integer"},
            },
            {
                "name": "status",
                "required": False,
                "in": "query",
                "description": "Filter by status (OPEN, CLOSED, PARTIAL)",
                "schema": {"type": "string", "enum": ["OPEN", "CLOSED", "PARTIAL"]},
            },
            {
                "name": "symbol",
                "required": False,
                "in": "query",
                "description": "Filter by instrument symbol",
                "schema": {"type": "string"},
            },
            {
                "name": "limit",
                "required": False,
                "in": "query",
                "description": "Number of positions to return (default: 50, max: 100)",
                "schema": {"type": "integer", "default": 50, "maximum": 100},
            },
            {
                "name": "offset",
                "required": False,
                "in": "query",
                "description": "Offset for pagination",
                "schema": {"type": "integer", "default": 0},
            },
        ],
        responses={
            200: OpenApiResponse(
                description="Trade history retrieved successfully",
                response={
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer"},
                        "results": {"type": "array", "items": PositionSerializer},
                    }
                }
            ),
        },
        summary="Get trade history",
        description="Get trade history for authenticated user with filtering and pagination"
    )
    def get(self, request):
        """Get trade history"""
        # Get user's accounts
        accounts = request.user.tradeaccount_set.all()
        if not accounts.exists():
            return Response(
                {"error": "No trading accounts found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build queryset
        queryset = Position.objects.filter(
            account__user=request.user
        ).select_related("instrument", "account").prefetch_related("logs").order_by("-opened_at")
        
        # Apply filters
        account_id = request.query_params.get("account_id")
        if account_id:
            try:
                account_id = int(account_id)
                queryset = queryset.filter(account_id=account_id)
            except ValueError:
                return Response(
                    {"error": "Invalid account_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        symbol = request.query_params.get("symbol")
        if symbol:
            queryset = queryset.filter(instrument__symbol__iexact=symbol.upper())
        
        # Pagination
        limit = min(int(request.query_params.get("limit", 50)), 100)
        offset = int(request.query_params.get("offset", 0))
        
        total_count = queryset.count()
        positions = queryset[offset:offset + limit]
        
        # Serialize
        serializer = PositionSerializer(positions, many=True)
        
        return Response({
            "count": total_count,
            "offset": offset,
            "limit": limit,
            "results": serializer.data
        })


class TradeEventsAPIView(APIView):
    """
    Get trade events (polling endpoint for Flutter)
    
    GET /api/trade/events/?account_id=123&since=2024-01-01T00:00:00Z&limit=100
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        parameters=[
            {
                "name": "account_id",
                "required": False,
                "in": "query",
                "description": "Filter by account ID",
                "schema": {"type": "integer"},
            },
            {
                "name": "since",
                "required": False,
                "in": "query",
                "description": "Get events since this timestamp (ISO format)",
                "schema": {"type": "string", "format": "date-time"},
            },
            {
                "name": "limit",
                "required": False,
                "in": "query",
                "description": "Number of events to return (default: 100, max: 500)",
                "schema": {"type": "integer", "default": 100, "maximum": 500},
            },
        ],
        responses={
            200: OpenApiResponse(
                description="Trade events retrieved successfully",
                response={
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer"},
                        "events": {"type": "array", "items": PositionLogSerializer},
                    }
                }
            ),
        },
        summary="Get trade events",
        description="Get trade events (OPEN, CLOSE, SL_HIT, TP_HIT) for polling or WebSocket integration"
    )
    def get(self, request):
        """Get trade events"""
        # Get user's accounts
        accounts = request.user.tradeaccount_set.all()
        if not accounts.exists():
            return Response(
                {"error": "No trading accounts found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build queryset
        queryset = PositionLog.objects.filter(
            position__account__user=request.user
        ).select_related("position", "position__instrument", "position__account").order_by("-created_at")
        
        # Filter by account
        account_id = request.query_params.get("account_id")
        if account_id:
            try:
                account_id = int(account_id)
                queryset = queryset.filter(position__account_id=account_id)
            except ValueError:
                return Response(
                    {"error": "Invalid account_id"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Filter by timestamp
        since = request.query_params.get("since")
        if since:
            try:
                since_dt = timezone.datetime.fromisoformat(since.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=since_dt)
            except ValueError:
                return Response(
                    {"error": "Invalid since format. Use ISO format."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Default: last 24 hours
            since_dt = timezone.now() - timedelta(hours=24)
            queryset = queryset.filter(created_at__gte=since_dt)
        
        # Limit
        limit = min(int(request.query_params.get("limit", 100)), 500)
        events = queryset[:limit]
        
        # Serialize
        serializer = PositionLogSerializer(events, many=True)
        
        return Response({
            "count": len(events),
            "since": since_dt.isoformat() if since else None,
            "events": serializer.data
        })
