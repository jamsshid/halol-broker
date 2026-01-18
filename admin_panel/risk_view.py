from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from rest_framework import serializers
from django.db.models import Q, F
from django.db import transaction

from accounts.models import Account, RiskLimit
from common.enums import AccountStatus
from django.db.models import Avg, Max, Min


class RiskAlertSerializer(serializers.Serializer):
    """Serializer for risk alert response"""
    account_id = serializers.UUIDField()
    account_number = serializers.CharField()
    user_email = serializers.EmailField()
    daily_loss_current = serializers.DecimalField(max_digits=18, decimal_places=2)
    max_daily_loss = serializers.DecimalField(max_digits=18, decimal_places=2, allow_null=True)
    loss_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    status = serializers.CharField()


class UpdateGlobalLimitsSerializer(serializers.Serializer):
    """Serializer for updating global limits"""
    max_leverage = serializers.IntegerField(required=False, min_value=1, max_value=1000)
    max_daily_loss_percent = serializers.DecimalField(
        required=False, 
        max_digits=5, 
        decimal_places=2,
        min_value=Decimal('0.01'),
        max_value=Decimal('100.00')
    )


class UpdateForbiddenInstrumentsSerializer(serializers.Serializer):
    """Serializer for updating forbidden instruments"""
    account_id = serializers.UUIDField()
    forbidden_instruments = serializers.ListField(
        child=serializers.CharField(),
        required=True
    )


class RiskAlertView(APIView):
    """
    Admin API to get list of users approaching daily loss limits
    Returns users where daily_loss_current >= 90% of max_daily_loss
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """
        Get list of accounts with high risk (daily_loss_current >= 90% of max_daily_loss)
        """
        # Get all active accounts with their risk limits
        accounts = Account.objects.filter(
            status=AccountStatus.ACTIVE.value
        ).select_related('user', 'risk_limits')

        alerts = []
        for account in accounts:
            # Calculate max daily loss limit
            max_loss_limit = None
            if account.max_daily_loss:
                # Use absolute amount from account
                max_loss_limit = account.max_daily_loss
            elif hasattr(account, 'risk_limits') and account.risk_limits.max_daily_loss_percent:
                # Calculate based on percentage of balance
                max_loss_limit = account.balance * account.risk_limits.max_daily_loss_percent / 100

            # Check if daily_loss_current >= 90% of max_daily_loss
            if max_loss_limit and max_loss_limit > 0:
                threshold = max_loss_limit * Decimal('0.90')
                if account.daily_loss_current >= threshold:
                    # Calculate loss percentage
                    loss_percentage = (account.daily_loss_current / max_loss_limit) * 100

                    alerts.append({
                        'account_id': str(account.id),
                        'account_number': account.account_number,
                        'user_email': account.user.email,
                        'daily_loss_current': str(account.daily_loss_current),
                        'max_daily_loss': str(account.max_daily_loss) if account.max_daily_loss else None,
                        'max_daily_loss_percent': str(account.risk_limits.max_daily_loss_percent) if hasattr(account, 'risk_limits') and account.risk_limits.max_daily_loss_percent else None,
                        'loss_percentage': str(loss_percentage.quantize(Decimal('0.01'))),
                        'status': account.status,
                        'balance': str(account.balance)
                    })

        return Response({
            'alerts': alerts,
            'count': len(alerts)
        }, status=status.HTTP_200_OK)


class UpdateGlobalLimitsView(APIView):
    """
    Admin API to update global risk limits for all users
    Updates max_leverage and/or max_daily_loss_percent for all accounts
    """
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request):
        """
        Update global limits for all accounts
        """
        serializer = UpdateGlobalLimitsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        max_leverage = serializer.validated_data.get('max_leverage')
        max_daily_loss_percent = serializer.validated_data.get('max_daily_loss_percent')

        updated_accounts = 0
        updated_risk_limits = 0

        if max_leverage is not None:
            # Update max_leverage for all accounts
            accounts_updated = Account.objects.update(max_leverage=max_leverage)
            updated_accounts += accounts_updated

            # Update max_leverage in RiskLimit as well
            risk_limits_updated = RiskLimit.objects.update(max_leverage=max_leverage)
            updated_risk_limits += risk_limits_updated

        if max_daily_loss_percent is not None:
            # Update max_daily_loss_percent in RiskLimit for all accounts
            risk_limits_updated = RiskLimit.objects.update(
                max_daily_loss_percent=max_daily_loss_percent
            )
            updated_risk_limits += risk_limits_updated

        return Response({
            'message': 'Global limits updated successfully',
            'accounts_updated': updated_accounts,
            'risk_limits_updated': updated_risk_limits,
            'updated_values': {
                'max_leverage': max_leverage,
                'max_daily_loss_percent': str(max_daily_loss_percent) if max_daily_loss_percent else None
            }
        }, status=status.HTTP_200_OK)


class UpdateForbiddenInstrumentsView(APIView):
    """
    Admin API to update forbidden_instruments list for a specific account
    """
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request):
        """
        Update forbidden_instruments for a specific account's RiskLimit
        """
        serializer = UpdateForbiddenInstrumentsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account_id = serializer.validated_data['account_id']
        forbidden_instruments = serializer.validated_data['forbidden_instruments']

        try:
            account = Account.objects.get(id=account_id)
            risk_limit, created = RiskLimit.objects.get_or_create(account=account)
            risk_limit.forbidden_instruments = forbidden_instruments
            risk_limit.save()

            return Response({
                'message': 'Forbidden instruments updated successfully',
                'account_id': str(account_id),
                'account_number': account.account_number,
                'forbidden_instruments': forbidden_instruments,
                'created': created
            }, status=status.HTTP_200_OK)

        except Account.DoesNotExist:
            return Response({
                'error': 'Account not found'
            }, status=status.HTTP_404_NOT_FOUND)


class GlobalRiskLimitAPI(APIView):
    """
    Global Enforcement: Admin API for viewing and updating global risk limits
    for all users (leverage and loss limits on global scale).
    
    GET: View current global limits statistics
    PUT/PATCH: Update global limits for all accounts
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """
        Get current global risk limit statistics across all accounts
        """
        # Get statistics from all accounts
        account_stats = Account.objects.aggregate(
            avg_max_leverage=Avg('max_leverage'),
            max_leverage_max=Max('max_leverage'),
            min_max_leverage=Min('max_leverage'),
            avg_max_daily_loss=Avg('max_daily_loss'),
        )

        # Get statistics from RiskLimit table
        risk_limit_stats = RiskLimit.objects.aggregate(
            avg_max_leverage=Avg('max_leverage'),
            avg_max_daily_loss_percent=Avg('max_daily_loss_percent'),
        )

        # Get most common values
        accounts_count = Account.objects.count()
        risk_limits_count = RiskLimit.objects.count()

        # Get default values from a sample account (if exists)
        sample_account = Account.objects.first()
        sample_risk_limit = RiskLimit.objects.first()

        response_data = {
            'accounts': {
                'total_count': accounts_count,
                'max_leverage': {
                    'average': float(account_stats['avg_max_leverage'] or 100),
                    'max': account_stats['max_leverage_max'] or 100,
                    'min': account_stats['min_max_leverage'] or 100,
                },
                'max_daily_loss': {
                    'average': float(account_stats['avg_max_daily_loss'] or 0),
                },
                'default_max_leverage': sample_account.max_leverage if sample_account else 100,
            },
            'risk_limits': {
                'total_count': risk_limits_count,
                'max_leverage': {
                    'average': float(risk_limit_stats['avg_max_leverage'] or 100),
                },
                'max_daily_loss_percent': {
                    'average': float(risk_limit_stats['avg_max_daily_loss_percent'] or 5.0),
                },
                'default_max_leverage': sample_risk_limit.max_leverage if sample_risk_limit else 100,
                'default_max_daily_loss_percent': float(
                    sample_risk_limit.max_daily_loss_percent if sample_risk_limit else 5.0
                ),
            },
        }

        return Response(response_data, status=status.HTTP_200_OK)

    @transaction.atomic
    def put(self, request):
        """
        Update global risk limits for ALL accounts and risk limits.
        Replaces UpdateGlobalLimitsView.post() functionality with PUT method.
        """
        return self._update_limits(request)

    @transaction.atomic
    def patch(self, request):
        """
        Partially update global risk limits (same as PUT for this endpoint).
        """
        return self._update_limits(request)

    def _update_limits(self, request):
        """
        Internal method to handle limit updates
        """
        serializer = UpdateGlobalLimitsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        max_leverage = serializer.validated_data.get('max_leverage')
        max_daily_loss_percent = serializer.validated_data.get('max_daily_loss_percent')

        updated_accounts = 0
        updated_risk_limits = 0

        if max_leverage is not None:
            # Update max_leverage for all accounts
            accounts_updated = Account.objects.update(max_leverage=max_leverage)
            updated_accounts += accounts_updated

            # Update max_leverage in RiskLimit as well
            risk_limits_updated = RiskLimit.objects.update(max_leverage=max_leverage)
            updated_risk_limits += risk_limits_updated

        if max_daily_loss_percent is not None:
            # Update max_daily_loss_percent in RiskLimit for all accounts
            risk_limits_updated = RiskLimit.objects.update(
                max_daily_loss_percent=max_daily_loss_percent
            )
            updated_risk_limits += risk_limits_updated

        # If max_daily_loss_percent is updated, optionally calculate and update
        # max_daily_loss on Account model for accounts that don't have it set
        if max_daily_loss_percent is not None:
            # This would update accounts where max_daily_loss is NULL
            # based on their current balance and the new percentage
            pass  # Optional: implement if needed

        return Response({
            'message': 'Global risk limits updated successfully for all accounts',
            'accounts_updated': updated_accounts,
            'risk_limits_updated': updated_risk_limits,
            'updated_values': {
                'max_leverage': max_leverage,
                'max_daily_loss_percent': str(max_daily_loss_percent) if max_daily_loss_percent else None
            }
        }, status=status.HTTP_200_OK)

