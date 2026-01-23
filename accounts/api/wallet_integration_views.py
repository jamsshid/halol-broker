from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from ..services.wallet_service import WalletService
from ..models import Account
from common.exceptions import InsufficientBalanceError, AccountSuspendedError, RiskLimitExceeded, DailyLossLimitExceeded


class WalletLockView(APIView):
    """
    Lock balance for trade
    Used by Backend 1 when opening position

    POST /api/wallet/lock/
    {
        "account_id": "uuid",
        "amount": "100.00",
        "trade_id": "uuid",
        "description": "Margin for EUR/USD"
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        account_id = request.data.get("account_id")
        amount = request.data.get("amount")
        trade_id = request.data.get("trade_id")
        description = request.data.get("description", "")

        if not all([account_id, amount, trade_id]):
            return Response(
                {"error": "account_id, amount, and trade_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = Account.objects.get(id=account_id, user=request.user)
        except Account.DoesNotExist:
            return Response(
                {"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Daily Loss QA: Check if daily loss limit exceeded before locking balance
        daily_loss_ok = WalletService.check_daily_loss_limit(account)
        if not daily_loss_ok:
            return Response(
                {
                    "error": f"Daily loss limit exceeded. Current: {account.daily_loss_current}, Limit: {account.max_daily_loss}. Balance locking rejected.",
                    "code": "RISK_LIMIT_EXCEEDED",
                    "daily_loss_current": str(account.daily_loss_current),
                    "daily_loss_max": str(account.max_daily_loss)
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            txn = WalletService.lock_balance(
                account_id=account_id,
                amount=amount,
                trade_id=trade_id,
                description=description,
            )

            return Response(
                {
                    "status": "success",
                    "transaction_id": txn.id,
                    "locked_amount": amount,
                    "available_balance": account.available_balance,
                }
            )
        except (InsufficientBalanceError, AccountSuspendedError, RiskLimitExceeded, DailyLossLimitExceeded) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class WalletReleaseView(APIView):
    """
    Release locked balance
    Used by Backend 1 when closing position

    POST /api/wallet/release/
    {
        "account_id": "uuid",
        "amount": "100.00",
        "trade_id": "uuid"
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        account_id = request.data.get("account_id")
        amount = request.data.get("amount")
        trade_id = request.data.get("trade_id")
        description = request.data.get("description", "")

        if not all([account_id, amount, trade_id]):
            return Response(
                {"error": "account_id, amount, and trade_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = Account.objects.get(id=account_id, user=request.user)
        except Account.DoesNotExist:
            return Response(
                {"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND
            )

        txn = WalletService.release_balance(
            account_id=account_id,
            amount=amount,
            trade_id=trade_id,
            description=description,
        )

        return Response(
            {
                "status": "success",
                "transaction_id": txn.id,
                "released_amount": amount,
                "available_balance": account.available_balance,
            }
        )


class WalletApplyPnLView(APIView):
    """
    Apply profit/loss to account
    Used by Backend 1 when closing trade

    POST /api/wallet/apply-pnl/
    {
        "account_id": "uuid",
        "pnl_amount": "50.00",  # positive for profit, negative for loss
        "trade_id": "uuid",
        "description": "Profit from EUR/USD trade"
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        account_id = request.data.get("account_id")
        pnl_amount = request.data.get("pnl_amount")
        trade_id = request.data.get("trade_id")
        description = request.data.get("description", "")

        if not all([account_id, pnl_amount, trade_id]):
            return Response(
                {"error": "account_id, pnl_amount, and trade_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = Account.objects.get(id=account_id, user=request.user)
        except Account.DoesNotExist:
            return Response(
                {"error": "Account not found"}, status=status.HTTP_404_NOT_FOUND
            )

        txn = WalletService.apply_pnl(
            account_id=account_id,
            pnl_amount=pnl_amount,
            trade_id=trade_id,
            description=description,
        )

        # Check if daily loss limit exceeded
        exceeded = not WalletService.check_daily_loss_limit(account)

        return Response(
            {
                "status": "success",
                "transaction_id": txn.id,
                "pnl_amount": pnl_amount,
                "new_balance": account.balance,
                "daily_loss_current": account.daily_loss_current,
                "daily_loss_limit_exceeded": exceeded,
            }
        )
