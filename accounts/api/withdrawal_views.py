from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import Withdrawal, Account
from ..serializers import WithdrawalSerializer, WithdrawalRequestSerializer
from ..services.withdrawal_service import WithdrawalService
from common.exceptions import InsufficientBalanceError


class WithdrawalViewSet(viewsets.ModelViewSet):
    """
    Withdrawal Management API

    Endpoints:
    - GET /api/withdrawals/ - List withdrawals
    - POST /api/withdrawals/ - Create withdrawal request
    - GET /api/withdrawals/{id}/ - Get withdrawal details
    - POST /api/withdrawals/{id}/cancel/ - Cancel pending withdrawal
    - GET /api/withdrawals/pending/ - Get pending withdrawals
    """

    serializer_class = WithdrawalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        accounts = Account.objects.filter(user=self.request.user)
        return Withdrawal.objects.filter(account__in=accounts).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        """Create withdrawal request"""
        serializer = WithdrawalRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account_id = serializer.validated_data["account_id"]

        # Verify account belongs to user
        try:
            account = Account.objects.get(id=account_id, user=request.user)
        except Account.DoesNotExist:
            return Response(
                {"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Real accounts must be verified
        if account.account_type == "real" and not request.user.is_verified:
            return Response(
                {"error": "Account must be verified for withdrawals"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            withdrawal = WithdrawalService.create_withdrawal(
                account_id=account_id,
                payment_method=serializer.validated_data["payment_method"],
                amount=serializer.validated_data["amount"],
                destination_address=serializer.validated_data["destination_address"],
                destination_details=serializer.validated_data.get(
                    "destination_details"
                ),
            )
        except InsufficientBalanceError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        response_data = WithdrawalSerializer(withdrawal).data
        response_data["note"] = (
            "Withdrawal request submitted. Approval typically takes 1-3 business days."
        )

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel pending withdrawal"""
        withdrawal = self.get_object()

        if withdrawal.status != "pending":
            return Response(
                {"error": "Only pending withdrawals can be cancelled"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        withdrawal.status = "cancelled"
        withdrawal.save()

        withdrawal.transaction.status = "cancelled"
        withdrawal.transaction.save()

        return Response({"status": "cancelled"})

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Get all pending withdrawals"""
        withdrawals = self.get_queryset().filter(status="pending")
        serializer = self.get_serializer(withdrawals, many=True)
        return Response(serializer.data)
