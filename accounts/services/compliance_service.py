"""
Compliance Service - Handles Sharia compliance violations and account freezing
"""
from django.db import transaction
from django.utils import timezone
from typing import Dict, Any, List
import logging

from ..models import Account, Transaction
from common.enums import TransactionType, ShariaContractType
from common.exceptions import ShariahComplianceError, AccountSuspendedError

logger = logging.getLogger(__name__)


class ComplianceService:
    """Service for Sharia compliance enforcement"""

    @staticmethod
    @transaction.atomic
    def freeze_account(
        account_id: str,
        reason: str,
        violation_type: str = "sharia_violation"
    ) -> Dict[str, Any]:
        """
        Freeze account due to Sharia compliance violation.
        
        Args:
            account_id: Account UUID
            reason: Reason for freezing
            violation_type: Type of violation
        
        Returns:
            Dict with freeze result
        """
        account = Account.objects.select_for_update().get(id=account_id)
        
        # Freeze account
        account.is_frozen = True
        account.freeze_reason = reason
        account.frozen_at = timezone.now()
        account.status = 'suspended'  # Change status to suspended
        account.save()
        
        logger.critical(
            f"Account {account.account_number} frozen due to {violation_type}: {reason}"
        )
        
        # Create notification for user
        from ..models import Notification, NotificationLevel
        Notification.objects.create(
            user=account.user,
            account=account,
            message=f"Account frozen: {reason}",
            level=NotificationLevel.CRITICAL.value,
            metadata={
                'violation_type': violation_type,
                'frozen_at': account.frozen_at.isoformat()
            }
        )
        
        return {
            'success': True,
            'account_id': str(account.id),
            'account_number': account.account_number,
            'is_frozen': True,
            'freeze_reason': reason,
            'frozen_at': account.frozen_at.isoformat()
        }

    @staticmethod
    @transaction.atomic
    def unfreeze_account(
        account_id: str,
        unfreeze_reason: str,
        unfrozen_by_user_id: str
    ) -> Dict[str, Any]:
        """
        Unfreeze account after compliance review.
        
        Args:
            account_id: Account UUID
            unfreeze_reason: Reason for unfreezing
            unfrozen_by_user_id: Admin user who unfroze the account
        
        Returns:
            Dict with unfreeze result
        """
        account = Account.objects.select_for_update().get(id=account_id)
        
        if not account.is_frozen:
            return {
                'success': False,
                'message': 'Account is not frozen'
            }
        
        # Unfreeze account
        account.is_frozen = False
        account.freeze_reason = ''
        account.status = 'active'  # Restore to active
        account.save()
        
        logger.info(
            f"Account {account.account_number} unfrozen by user {unfrozen_by_user_id}: {unfreeze_reason}"
        )
        
        return {
            'success': True,
            'account_id': str(account.id),
            'account_number': account.account_number,
            'is_frozen': False,
            'unfrozen_at': timezone.now().isoformat()
        }

    @staticmethod
    def check_compliance_violation(account_id: str) -> List[Dict[str, Any]]:
        """
        Check for Sharia compliance violations in account transactions.
        
        Args:
            account_id: Account UUID
        
        Returns:
            List of violations found
        """
        account = Account.objects.get(id=account_id)
        violations = []
        
        # Check for transactions without Sharia contract type
        transactions_without_contract = Transaction.objects.filter(
            account=account,
            sharia_contract_type__isnull=True
        ).exclude(
            transaction_type__in=[TransactionType.TRADE_LOCK.value, TransactionType.TRADE_RELEASE.value]
        )
        
        if transactions_without_contract.exists():
            violations.append({
                'type': 'missing_contract_type',
                'severity': 'high',
                'count': transactions_without_contract.count(),
                'message': f'{transactions_without_contract.count()} transactions missing Sharia contract type'
            })
        
        # Check for SWAP transactions (Riba indicator)
        swap_transactions = Transaction.objects.filter(
            account=account,
            transaction_type=TransactionType.SWAP.value
        )
        
        if swap_transactions.exists():
            violations.append({
                'type': 'swap_transactions',
                'severity': 'critical',
                'count': swap_transactions.count(),
                'message': f'{swap_transactions.count()} SWAP transactions found (Riba violation)'
            })
        
        # Check for interest-like fee patterns
        # (fees that are fixed percentage unrelated to trading)
        suspicious_fees = Transaction.objects.filter(
            account=account,
            transaction_type__in=[TransactionType.FEE.value, TransactionType.COMMISSION.value],
            amount__gt=0
        )
        
        # If account is Sharia compliant but has many fees, flag it
        if account.is_shariat_compliant and suspicious_fees.count() > 10:
            violations.append({
                'type': 'excessive_fees',
                'severity': 'medium',
                'count': suspicious_fees.count(),
                'message': 'Excessive fees detected for Sharia-compliant account'
            })
        
        return violations

    @staticmethod
    def validate_transaction_compliance(transaction: Transaction) -> bool:
        """
        Validate transaction for Sharia compliance.
        
        Args:
            transaction: Transaction instance
        
        Returns:
            bool: True if compliant
        
        Raises:
            ShariahComplianceError: If violation detected
        """
        account = transaction.account
        
        # Check if account is frozen
        if account.is_frozen:
            raise AccountSuspendedError(
                f"Account {account.account_number} is frozen: {account.freeze_reason}"
            )
        
        # For Sharia-compliant accounts, require contract type
        if account.is_shariat_compliant:
            if not transaction.sharia_contract_type:
                raise ShariahComplianceError(
                    "Sharia-compliant account requires sharia_contract_type for all transactions",
                    details={
                        'transaction_id': str(transaction.id),
                        'account_id': str(account.id)
                    }
                )
            
            # Block SWAP transactions
            if transaction.transaction_type == TransactionType.SWAP.value:
                # Auto-freeze account on SWAP transaction
                ComplianceService.freeze_account(
                    account_id=str(account.id),
                    reason="SWAP transaction detected (Riba violation)",
                    violation_type="riba_violation"
                )
                raise ShariahComplianceError(
                    "SWAP transactions are prohibited for Sharia-compliant accounts",
                    details={
                        'transaction_id': str(transaction.id),
                        'account_frozen': True
                    }
                )
        
        return True

