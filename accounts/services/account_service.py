"""
Account Service - Handles account switching and mode synchronization
"""
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import Optional, Dict, Any
import logging

from ..models import Account, User
from common.enums import AccountType, ComplianceMode, CalmMode
from common.exceptions import InvalidAccountTypeError, AccountSuspendedError

logger = logging.getLogger(__name__)


class AccountService:
    """Service for managing account switching and mode synchronization"""

    @staticmethod
    @transaction.atomic
    def switch_account(
        user: User,
        target_account_type: str,
        validate_balance: bool = True
    ) -> Dict[str, Any]:
        """
        Switch user's current account context between Demo and Real.
        
        Args:
            user: User instance
            target_account_type: 'demo' or 'real'
            validate_balance: Whether to validate account balance before switching
        
        Returns:
            Dict with account info and updated context
        """
        # Validate account type
        if target_account_type not in [AccountType.DEMO.value, AccountType.REAL.value]:
            raise InvalidAccountTypeError(
                f"Invalid account type: {target_account_type}. Must be 'demo' or 'real'"
            )

        # Get or create target account
        account, created = Account.objects.get_or_create(
            user=user,
            account_type=target_account_type,
            defaults={
                'status': 'active' if target_account_type == AccountType.DEMO.value else 'pending_kyc',
                'balance': Decimal('10000.00') if target_account_type == AccountType.DEMO.value else Decimal('0.00'),
            }
        )

        if created:
            logger.info(f"Created new {target_account_type} account for user {user.id}")

        # Validate account status
        if account.status not in ['active', 'pending_kyc']:
            raise AccountSuspendedError(
                f"Cannot switch to {target_account_type} account: status is {account.status}"
            )

        # Validate balance if required
        if validate_balance and target_account_type == AccountType.REAL.value:
            if account.balance < Decimal('0.00'):
                raise InvalidAccountTypeError(
                    "Cannot switch to Real account: negative balance detected"
                )

        # Update user's last active account (stored in session/JWT context)
        # This will be used by middleware to determine current account
        user_metadata = getattr(user, 'metadata', {}) or {}
        user_metadata['current_account_id'] = str(account.id)
        user_metadata['current_account_type'] = target_account_type
        user_metadata['last_account_switch'] = timezone.now().isoformat()
        
        # Store in user model if there's a metadata field, otherwise use session
        # For now, we'll return it in the response and let the client store it

        logger.info(
            f"User {user.id} switched to {target_account_type} account {account.id}"
        )

        return {
            'account_id': str(account.id),
            'account_number': account.account_number,
            'account_type': account.account_type,
            'status': account.status,
            'balance': str(account.balance),
            'available_balance': str(account.available_balance),
            'switched_at': timezone.now().isoformat(),
            'context': {
                'current_account_id': str(account.id),
                'current_account_type': target_account_type,
            }
        }

    @staticmethod
    def get_current_account(user: User, account_type: Optional[str] = None) -> Account:
        """
        Get user's current active account.
        
        Args:
            user: User instance
            account_type: Optional account type to filter by
        
        Returns:
            Account instance
        """
        if account_type:
            try:
                return Account.objects.get(user=user, account_type=account_type, status='active')
            except Account.DoesNotExist:
                # Fallback to demo account
                return Account.objects.get(user=user, account_type=AccountType.DEMO.value)
        
        # Try to get from user metadata or default to demo
        # For now, default to demo if no preference
        try:
            return Account.objects.get(user=user, account_type=AccountType.DEMO.value)
        except Account.DoesNotExist:
            # Create demo account if it doesn't exist
            return Account.objects.create(
                user=user,
                account_type=AccountType.DEMO.value,
                account_number=f"D{timezone.now().strftime('%Y%m%d%H%M%S')}",
                balance=Decimal('10000.00'),
                status='active'
            )

    @staticmethod
    def validate_trade_request(
        account: Account,
        requested_account_type: str,
        required_balance: Decimal
    ) -> bool:
        """
        Validate trade request matches account type and has sufficient balance.
        Used by Backend 1 before opening trades.
        
        Args:
            account: Account instance
            requested_account_type: Account type from trade request
            required_balance: Required balance for the trade
        
        Returns:
            bool: True if valid
        
        Raises:
            InvalidAccountTypeError: If account type mismatch
            InsufficientBalanceError: If insufficient balance
        """
        from common.exceptions import InsufficientBalanceError

        # Validate account type match
        if account.account_type != requested_account_type:
            raise InvalidAccountTypeError(
                f"Account type mismatch: account is {account.account_type}, "
                f"but trade requested {requested_account_type}"
            )

        # Validate account status
        if account.status != 'active':
            raise AccountSuspendedError(
                f"Cannot trade on account with status: {account.status}"
            )

        # Validate balance
        if account.available_balance < required_balance:
            raise InsufficientBalanceError(
                f"Insufficient balance. Available: {account.available_balance}, "
                f"Required: {required_balance}"
            )

        return True

