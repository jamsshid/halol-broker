from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Avg
from decimal import Decimal
from ..models import Account, Wallet, Transaction, RiskLimit
from ..serializers import AccountSerializer, WalletSerializer, TransactionSerializer, RiskLimitSerializer
from ..services.wallet_service import WalletService
from common.constants import RiskLimits

class AccountViewSet(viewsets.ModelViewSet):
    """
    Account Management API
    
    Endpoints:
    - GET /api/accounts/ - List user accounts
    - POST /api/accounts/ - Create new account (demo/real)
    - GET /api/accounts/{id}/ - Get account details
    - GET /api/accounts/{id}/wallet/ - Get wallet info
    - GET /api/accounts/{id}/check_risk_limits/ - Check risk status
    - GET /api/accounts/{id}/statistics/ - Get account statistics
    """
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Account.objects.filter(user=self.request.user).select_related('wallet')
    
    def create(self, request, *args, **kwargs):
        """Create new trading account"""
        account_type = request.data.get('account_type', 'demo')
        is_shariat = request.data.get('is_shariat_compliant', False)
        
        # Check if user already has this account type
        existing = Account.objects.filter(
            user=request.user,
            account_type=account_type
        ).exists()
        
        if existing:
            return Response(
                {'error': f'You already have a {account_type} account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate account number
        import random
        account_number = f"{account_type[:1].upper()}{random.randint(10000000, 99999999)}"
        
        # Set initial balance for demo
        initial_balance = Decimal('10000.00') if account_type == 'demo' else Decimal('0.00')
        
        account = Account.objects.create(
            user=request.user,
            account_type=account_type,
            account_number=account_number,
            balance=initial_balance,
            is_shariat_compliant=is_shariat,
            swap_free=is_shariat,
            max_leverage=50 if is_shariat else 100,
            status='active' if account_type == 'demo' else 'pending_kyc'
        )
        
        # Create wallet
        Wallet.objects.create(account=account)
        
        # Create risk limits
        RiskLimit.objects.create(
            account=account,
            max_leverage=account.max_leverage,
            max_overnight_exposure_percent=Decimal('50.0') if is_shariat else None
        )
        
        serializer = self.get_serializer(account)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def wallet(self, request, pk=None):
        """Get wallet details with statistics"""
        account = self.get_object()
        wallet = Wallet.objects.get(account=account)
        
        # Add additional stats
        data = WalletSerializer(wallet).data
        data['net_profit'] = wallet.total_profit - wallet.total_loss
        data['profit_ratio'] = (
            float(wallet.total_profit / wallet.total_loss) 
            if wallet.total_loss > 0 else 0
        )
        
        return Response(data)
    
    @action(detail=True, methods=['get'])
    def check_risk_limits(self, request, pk=None):
        """
        Check if account can open new position
        Used by Backend 1 before opening trades
        """
        account = self.get_object()
        risk_limits = RiskLimit.objects.get(account=account)
        
        # Check daily loss
        daily_loss_ok = WalletService.check_daily_loss_limit(account)
        
        # Check margin level
        margin_ok = account.margin_level > 100  # Minimum 100% margin level
        
        # Calculate available margin
        available_margin = account.available_balance
        max_position_size = (account.balance * risk_limits.max_position_size_percent) / 100
        
        return Response({
            'can_trade': daily_loss_ok and margin_ok and account.status == 'active',
            'daily_loss_limit_ok': daily_loss_ok,
            'daily_loss_current': account.daily_loss_current,
            'daily_loss_max': account.max_daily_loss,
            'margin_level': account.margin_level,
            'margin_ok': margin_ok,
            'available_balance': account.available_balance,
            'available_margin': available_margin,
            'max_position_size': max_position_size,
            'max_leverage': risk_limits.max_leverage,
            'max_open_positions': risk_limits.max_open_positions,
            'status': account.status
        })
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get detailed account statistics"""
        account = self.get_object()
        wallet = Wallet.objects.get(account=account)
        
        # Get transaction stats
        trades = Transaction.objects.filter(
            account=account,
            transaction_type='trade_pnl'
        )
        
        winning_trades = trades.filter(amount__gt=0).count()
        losing_trades = trades.filter(amount__lt=0).count()
        total_trades = winning_trades + losing_trades
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_profit = trades.filter(amount__gt=0).aggregate(
            avg=Avg('amount')
        )['avg'] or Decimal('0.00')
        
        avg_loss = trades.filter(amount__lt=0).aggregate(
            avg=Avg('amount')
        )['avg'] or Decimal('0.00')
        
        return Response({
            'account_number': account.account_number,
            'account_type': account.account_type,
            'balance': account.balance,
            'equity': account.equity,
            'total_deposits': wallet.total_deposits,
            'total_withdrawals': wallet.total_withdrawals,
            'total_profit': wallet.total_profit,
            'total_loss': wallet.total_loss,
            'net_profit': wallet.total_profit - wallet.total_loss,
            'total_fees': wallet.total_fees_paid,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': round(win_rate, 2),
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'profit_factor': float(wallet.total_profit / wallet.total_loss) if wallet.total_loss > 0 else 0
        })

class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Transaction History API
    
    Endpoints:
    - GET /api/transactions/ - List all transactions
    - GET /api/transactions/{id}/ - Get transaction details
    - GET /api/transactions/by_type/?type=deposit - Filter by type
    - GET /api/transactions/by_account/{account_id}/ - Filter by account
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        accounts = Account.objects.filter(user=self.request.user)
        queryset = Transaction.objects.filter(account__in=accounts)
        
        # Filter by type
        txn_type = self.request.query_params.get('type')
        if txn_type:
            queryset = queryset.filter(transaction_type=txn_type)
        
        # Filter by status
        txn_status = self.request.query_params.get('status')
        if txn_status:
            queryset = queryset.filter(status=txn_status)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def by_account(self, request):
        """Get transactions for specific account"""
        account_id = request.query_params.get('account_id')
        if not account_id:
            return Response(
                {'error': 'account_id required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transactions = Transaction.objects.filter(
            account_id=account_id,
            account__user=request.user
        ).order_by('-created_at')[:100]
        
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)