from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework import status
from django.db.models import Sum, Q, Count
from django.db.models.functions import Coalesce

from accounts.models import Account, User
from common.enums import AccountType, AccountStatus


class AdminFinancialStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        """
        Calculate and return global financial metrics:
        - total_real_balance: Total balance of all REAL accounts
        - total_demo_balance: Total balance of all DEMO accounts
        - exposure_ratio: locked_balance / total_balance ratio
        - kyc_summary: Count of users by KYC status
        """
        # Calculate total_real_balance
        total_real_balance = Account.objects.filter(
            account_type=AccountType.REAL.value
        ).aggregate(
            total=Coalesce(Sum('balance'), Decimal('0.00'))
        )['total']

        # Calculate total_demo_balance
        total_demo_balance = Account.objects.filter(
            account_type=AccountType.DEMO.value
        ).aggregate(
            total=Coalesce(Sum('balance'), Decimal('0.00'))
        )['total']

        # Calculate exposure_ratio (locked_balance / total_balance)
        total_locked = Account.objects.aggregate(
            total=Coalesce(Sum('locked_balance'), Decimal('0.00'))
        )['total']
        
        total_balance = Account.objects.aggregate(
            total=Coalesce(Sum('balance'), Decimal('0.00'))
        )['total']

        exposure_ratio = Decimal('0.00')
        if total_balance > 0:
            exposure_ratio = (total_locked / total_balance) * 100
            exposure_ratio = exposure_ratio.quantize(Decimal('0.01'))

        # Calculate KYC summary
        kyc_summary = User.objects.aggregate(
            pending=Count('id', filter=Q(kyc_status='pending')),
            verified=Count('id', filter=Q(kyc_status='verified')),
            rejected=Count('id', filter=Q(kyc_status='rejected'))
        )

        return Response({
            'total_real_balance': str(total_real_balance),
            'total_demo_balance': str(total_demo_balance),
            'exposure_ratio': str(exposure_ratio),
            'kyc_summary': {
                'pending': kyc_summary['pending'],
                'verified': kyc_summary['verified'],
                'rejected': kyc_summary['rejected']
            },
            'total_locked_balance': str(total_locked),
            'total_balance': str(total_balance)
        }, status=status.HTTP_200_OK)

