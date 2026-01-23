"""
Management command to audit wallet consistency.

This script compares the sum of all Transactions with Wallet.balance
and alerts admin panel if discrepancies are found.

Usage:
    python manage.py audit_wallets
    python manage.py audit_wallets --account-id <uuid>
    python manage.py audit_wallets --critical-only
"""
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import Account, Wallet, Transaction
from accounts.services.wallet_service import WalletService
from admin_panel.models import AuditLog
from common.enums import TransactionStatus


class Command(BaseCommand):
    help = 'Audit wallet consistency: Compare Transaction sum with Wallet.balance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id',
            type=str,
            help='Audit specific account by UUID',
        )
        parser.add_argument(
            '--critical-only',
            action='store_true',
            help='Only report critical discrepancies',
        )
        parser.add_argument(
            '--auto-fix',
            action='store_true',
            help='Automatically fix discrepancies (use with caution)',
        )

    def handle(self, *args, **options):
        account_id = options.get('account_id')
        critical_only = options.get('critical_only', False)
        auto_fix = options.get('auto_fix', False)

        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Wallet Consistency Audit Started ===\n'
                f'Timestamp: {timezone.now().isoformat()}\n'
            )
        )

        if account_id:
            # Audit specific account
            try:
                account = Account.objects.get(id=account_id)
                self.audit_account(account, critical_only, auto_fix)
            except Account.DoesNotExist:
                raise CommandError(f'Account with ID {account_id} not found')
        else:
            # Audit all accounts
            accounts = Account.objects.select_related('wallet').all()
            total_accounts = accounts.count()
            self.stdout.write(f'Auditing {total_accounts} accounts...\n')

            discrepancies_found = 0
            critical_discrepancies = 0

            for idx, account in enumerate(accounts, 1):
                self.stdout.write(
                    f'[{idx}/{total_accounts}] Auditing account: {account.account_number}',
                    ending=''
                )
                
                result = self.audit_account(account, critical_only, auto_fix)
                
                if not result['is_consistent']:
                    discrepancies_found += 1
                    if result['severity'] == 'critical':
                        critical_discrepancies += 1
                    self.stdout.write(
                        self.style.WARNING(f' - DISCREPANCY FOUND')
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(' - OK')
                    )

            # Summary
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n=== Audit Complete ===\n'
                    f'Total accounts audited: {total_accounts}\n'
                    f'Discrepancies found: {discrepancies_found}\n'
                    f'Critical discrepancies: {critical_discrepancies}\n'
                )
            )

    def audit_account(self, account, critical_only=False, auto_fix=False):
        """
        Audit a single account's wallet consistency.
        
        Returns:
            dict: Audit result with is_consistent, severity, difference, etc.
        """
        try:
            wallet = Wallet.objects.get(account=account)
        except Wallet.DoesNotExist:
            # Create wallet if it doesn't exist
            wallet = Wallet.objects.create(account=account)
            self.stdout.write(
                self.style.WARNING(f'  Created missing wallet for account {account.account_number}')
            )

        # Use WalletService.audit_balance for consistency
        audit_result = WalletService.audit_balance(account.id)

        if 'error' in audit_result:
            # Account not found or other error
            severity = 'warning'
            is_consistent = False
            difference = Decimal('0.00')
            message = audit_result.get('error', 'Unknown error')
        else:
            is_consistent = audit_result['is_consistent']
            difference = abs(audit_result['difference'])
            
            # Determine severity
            if is_consistent:
                severity = 'info'
                message = f"Account {account.account_number}: Balance consistent"
            elif difference > Decimal('100.00'):
                severity = 'critical'
                message = (
                    f"CRITICAL DISCREPANCY: Account {account.account_number} "
                    f"has balance mismatch of {difference}"
                )
            elif difference > Decimal('1.00'):
                severity = 'warning'
                message = (
                    f"Warning: Account {account.account_number} "
                    f"has balance mismatch of {difference}"
                )
            else:
                severity = 'info'
                message = (
                    f"Minor rounding difference: Account {account.account_number} "
                    f"difference: {difference}"
                )

        # Skip non-critical if critical_only flag is set
        if critical_only and severity != 'critical':
            return {
                'is_consistent': is_consistent,
                'severity': severity,
                'skipped': True
            }

        # Create audit log entry
        audit_log = AuditLog.objects.create(
            audit_type='wallet_consistency',
            severity=severity,
            account_id=account.id,
            account_number=account.account_number,
            is_consistent=is_consistent,
            expected_value=audit_result.get('calculated_balance'),
            actual_value=audit_result.get('account_balance'),
            difference=difference,
            message=message,
            details={
                'transaction_count': audit_result.get('transaction_count', 0),
                'transaction_sum': str(audit_result.get('transaction_sum', '0.00')),
                'initial_balance': str(audit_result.get('initial_balance', '0.00')),
                'account_balance': str(audit_result.get('account_balance', '0.00')),
                'calculated_balance': str(audit_result.get('calculated_balance', '0.00')),
            }
        )

        # Auto-fix if requested and discrepancy is critical
        if auto_fix and not is_consistent and severity == 'critical':
            self.stdout.write(
                self.style.WARNING(f'  Attempting auto-fix for account {account.account_number}...')
            )
            try:
                # Fix: Update account balance to match calculated balance
                calculated_balance = audit_result.get('calculated_balance', Decimal('0.00'))
                account.balance = calculated_balance
                account.save()
                
                audit_log.details['auto_fixed'] = True
                audit_log.details['fixed_balance'] = str(calculated_balance)
                audit_log.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'  Auto-fixed: Updated balance to {calculated_balance}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  Auto-fix failed: {str(e)}')
                )
                audit_log.details['auto_fix_error'] = str(e)
                audit_log.save()

        # Alert admin panel for critical discrepancies
        if severity == 'critical':
            self.stdout.write(
                self.style.ERROR(
                    f'\n⚠️  CRITICAL DISCREPANCY ALERT ⚠️\n'
                    f'Account: {account.account_number}\n'
                    f'Expected Balance: {audit_result.get("calculated_balance")}\n'
                    f'Actual Balance: {audit_result.get("account_balance")}\n'
                    f'Difference: {difference}\n'
                    f'Audit Log ID: {audit_log.id}\n'
                )
            )

        return {
            'is_consistent': is_consistent,
            'severity': severity,
            'difference': difference,
            'audit_log_id': str(audit_log.id),
            'message': message
        }

