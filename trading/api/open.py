from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class TradeOpenAPIView(APIView):

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "side": {"type": "string", "enum": ["BUY", "SELL"]},
                    "mode": {"type": "string", "enum": ["ULTRA", "SEMI"]},
                    "entry_price": {"type": "number"},
                    "stop_loss": {"type": "number"},
                    "take_profit": {"type": "number"},
                    "risk_percent": {"type": "number"},
                },
                "required": ["symbol", "side", "mode", "entry_price", "stop_loss", "risk_percent"]
            }
        },
        responses={200: dict}
    )
    def post(self, request):
        ...
