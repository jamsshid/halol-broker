from decimal import Decimal
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from django.db.models import Sum, Q
from django.db.models.functions import TruncDate, Coalesce
from django.utils import timezone

from accounts.models import Wallet, Transaction
from common.enums import TransactionType


class RevenueReportView(APIView):
    """
    Admin API for platform revenue monitoring
    Requires IsAdminUser permission
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """
        Calculate and return platform revenue metrics:
        - total_revenue: Sum of all total_fees_paid from wallets
        - fee_transactions: FEE transactions aggregated by time period
        - monthly_revenue_data: Monthly revenue for frontend charts
        """
        # Get total revenue from Wallet.total_fees_paid
        total_revenue = Wallet.objects.aggregate(
            total=Coalesce(Sum('total_fees_paid'), Decimal('0.00'))
        )['total']

        # Get query parameters for filtering
        period = request.query_params.get('period', 'monthly')  # daily, weekly, monthly
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # Base queryset for FEE transactions
        fee_transactions = Transaction.objects.filter(
            transaction_type=TransactionType.FEE.value,
            status='completed'  # Only count completed transactions
        )

        # Apply date filters if provided
        if start_date:
            try:
                start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                fee_transactions = fee_transactions.filter(created_at__gte=start_date_obj)
            except ValueError:
                pass

        if end_date:
            try:
                end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                fee_transactions = fee_transactions.filter(created_at__lte=end_date_obj)
            except ValueError:
                pass

        # Aggregate by period
        if period == 'daily':
            # Daily aggregation
            daily_data = fee_transactions.annotate(
                date=TruncDate('created_at')
            ).values('date').annotate(
                total_fees=Coalesce(Sum('amount'), Decimal('0.00'))
            ).order_by('date')

            fee_transactions_data = [
                {
                    'date': item['date'].isoformat() if item['date'] else None,
                    'amount': str(abs(item['total_fees']))  # Fees are negative, use abs
                }
                for item in daily_data
            ]

        elif period == 'weekly':
            # Weekly aggregation (last 12 weeks)
            weeks_ago = timezone.now() - timedelta(weeks=12)
            weekly_data = fee_transactions.filter(
                created_at__gte=weeks_ago
            ).extra(
                select={'week_start': "DATE_TRUNC('week', created_at)"}
            ).values('week_start').annotate(
                total_fees=Coalesce(Sum('amount'), Decimal('0.00'))
            ).order_by('week_start')

            fee_transactions_data = [
                {
                    'week': item['week_start'].isoformat() if item['week_start'] else None,
                    'amount': str(abs(item['total_fees']))
                }
                for item in weekly_data
            ]

        else:  # monthly (default)
            # Monthly aggregation for frontend charts
            monthly_data = fee_transactions.extra(
                select={'year_month': "DATE_TRUNC('month', created_at)"}
            ).values('year_month').annotate(
                total_fees=Coalesce(Sum('amount'), Decimal('0.00'))
            ).order_by('year_month')

            fee_transactions_data = [
                {
                    'month': item['year_month'].isoformat() if item['year_month'] else None,
                    'amount': str(abs(item['total_fees']))
                }
                for item in monthly_data
            ]

        # Verify Shariat compliance: fees should be service fees, not interest
        # Check that all accounts with fees have is_shariat_compliant flag properly set
        shariat_compliant_check = Transaction.objects.filter(
            transaction_type=TransactionType.FEE.value
        ).select_related('account').values_list(
            'account__is_shariat_compliant', flat=True
        ).distinct()

        # Monthly revenue data formatted for frontend charts (always return monthly for frontend)
        if period != 'monthly':
            # Also get monthly data for frontend charts
            monthly_data = Transaction.objects.filter(
                transaction_type=TransactionType.FEE.value,
                status='completed'
            ).extra(
                select={'year_month': "DATE_TRUNC('month', created_at)"}
            ).values('year_month').annotate(
                total_fees=Coalesce(Sum('amount'), Decimal('0.00'))
            ).order_by('year_month')
            
            monthly_revenue_data = [
                {
                    'month': item['year_month'].isoformat() if item['year_month'] else None,
                    'amount': str(abs(item['total_fees']))
                }
                for item in monthly_data
            ]
        else:
            monthly_revenue_data = fee_transactions_data

        return Response({
            'total_revenue': str(total_revenue),
            'period': period,
            'fee_transactions': fee_transactions_data,
            'monthly_revenue_data': monthly_revenue_data,
            'shariat_compliant': all(shariat_compliant_check) if shariat_compliant_check else True,
            'note': 'Fees are service charges, not interest-based (is_shariat_compliant verified)'
        }, status=status.HTTP_200_OK)

