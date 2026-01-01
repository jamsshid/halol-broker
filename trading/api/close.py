from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from trading.models import Position


class TradeCloseAPIView(APIView):
    """
    Trade CLOSE (skeleton)
    PnL keyingi bosqichda hisoblanadi
    """

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "position_id": {"type": "integer"},
                },
                "required": ["position_id"]
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "position_id": {"type": "integer"},
                    "status": {"type": "string"},
                }
            }
        }
    )
    def post(self, request):
        position_id = request.data.get("position_id")

        if not position_id:
            return Response(
                {"error": "position_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            position = Position.objects.get(
                id=position_id,
                status=Position.Status.OPEN
            )
        except Position.DoesNotExist:
            return Response(
                {"error": "Open position not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Skeleton close (PnL keyin qo‘shiladi)
        position.status = Position.Status.CLOSED
        position.save(update_fields=["status"])

        return Response(
            {
                "position_id": position.id,
                "status": "CLOSED"
            },
            status=status.HTTP_200_OK
        )
