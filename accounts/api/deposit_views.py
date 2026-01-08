from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import Deposit, Account
from ..serializers import DepositSerializer, DepositRequestSerializer
from ..services.deposit_service import DepositService


class DepositViewSet(viewsets.ModelViewSet):

    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        accounts = Account.objects.filter(user=self.request.user)
        return Deposit.objects.filter(account__in=accounts).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        """Create deposit request"""
        serializer = DepositRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account_id = serializer.validated_data["account_id"]

        # Verify account belongs to user
        try:
            account = Account.objects.get(id=account_id, user=request.user)
        except Account.DoesNotExist:
            return Response(
                {"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Create deposit
        deposit = DepositService.create_deposit(
            account_id=account_id,
            payment_method=serializer.validated_data["payment_method"],
            amount=serializer.validated_data["amount"],
            currency=serializer.validated_data.get("currency", "USD"),
            crypto_address=serializer.validated_data.get("crypto_address", ""),
        )

        # TODO: Integrate with payment gateway
        # For now, return deposit details with payment instructions

        response_data = DepositSerializer(deposit).data
        response_data["payment_instructions"] = self._get_payment_instructions(deposit)

        return Response(response_data, status=status.HTTP_201_CREATED)

    def _get_payment_instructions(self, deposit):
        """Generate payment instructions based on method"""
        if deposit.payment_method == "crypto_btc":
            return {
                "address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                "amount": str(deposit.amount),
                "network": "Bitcoin",
                "note": "Send exact amount to the address above",
            }
        elif deposit.payment_method == "crypto_eth":
            return {
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
                "amount": str(deposit.amount),
                "network": "Ethereum",
                "note": "Send exact amount to the address above",
            }
        elif deposit.payment_method in ["visa", "mastercard"]:
            return {
                "redirect_url": f"/payment/card/{deposit.id}",
                "note": "You will be redirected to secure payment page",
            }
        else:
            return {"note": "Please contact support for payment instructions"}

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Cancel pending deposit"""
        deposit = self.get_object()

        if deposit.status != "pending":
            return Response(
                {"error": "Only pending deposits can be cancelled"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deposit.status = "cancelled"
        deposit.save()

        deposit.transaction.status = "cancelled"
        deposit.transaction.save()

        return Response({"status": "cancelled"})

    @action(detail=False, methods=["get"])
    def pending(self, request):
        """Get all pending deposits"""
        deposits = self.get_queryset().filter(status="pending")
        serializer = self.get_serializer(deposits, many=True)
        return Response(serializer.data)
