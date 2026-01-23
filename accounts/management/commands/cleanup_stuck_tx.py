"""
Management command to cleanup stuck transactions after system crash.

Finds transactions in PROCESSING or PENDING status that are older than threshold
and safely rolls them back or completes them.

Usage:
    python manage.py cleanup_stuck_tx
    python manage.py cleanup_stuck_tx --threshold-hours 24
    python manage.py cleanup_stuck_tx --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from accounts.models import Transaction, Account
from accounts.services.wallet_service import WalletService
from common.enums import TransactionType, TransactionStatus


class Command(BaseCommand):
    help = 'Cleanup stuck transactions after system crash'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold-hours',
            type=int,
            default=24,
            help='Hours threshold for considering transaction stuck (default: 24)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )
        parser.add_argument(
            '--auto-fix',
            action='store_true',
            help='Automatically fix stuck transactions',
        )

    def handle(self, *args, **options):
        threshold_hours = options['threshold_hours']
        dry_run = options['dry_run']
        auto_fix = options['auto_fix']

        threshold_time = timezone.now() - timedelta(hours=threshold_hours)

        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Stuck Transaction Cleanup Started ===\n'
                f'Threshold: {threshold_hours} hours ago ({threshold_time.isoformat()})\n'
                f'Dry run: {dry_run}\n'
                f'Auto-fix: {auto_fix}\n'
            )
        )

        # Find stuck transactions
        stuck_txns = Transaction.objects.filter(
            status__in=[TransactionStatus.PROCESSING.value, TransactionStatus.PENDING.value],
            created_at__lt=threshold_time
        ).select_related('account').order_by('created_at')

        total_stuck = stuck_txns.count()
        self.stdout.write(f'Found {total_stuck} potentially stuck transactions\n')

        if total_stuck == 0:
            self.stdout.write(self.style.SUCCESS('No stuck transactions found. Exiting.'))
            return

        fixed_count = 0
        rolled_back_count = 0
        error_count = 0

        for txn in stuck_txns:
            self.stdout.write(
                f'Processing: {txn.id} - {txn.transaction_type} - '
                f'{txn.status} - Created: {txn.created_at}'
            )

            try:
                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  [DRY RUN] Would process transaction {txn.id}'
                        )
                    )
                    continue

                # Determine action based on transaction type
                if txn.transaction_type == TransactionType.DEPOSIT.value:
                    # Rollback deposit - it was never completed
                    if auto_fix:
                        txn.status = TransactionStatus.FAILED.value
                        txn.description = f'Rolled back stuck transaction (stuck for {threshold_hours}h)'
                        txn.save()
                        rolled_back_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Rolled back deposit transaction')
                        )

                elif txn.transaction_type == TransactionType.WITHDRAW.value:
                    # Check if withdrawal was partially processed
                    account = txn.account
                    # If balance was already deducted, we need to restore it
                    if txn.amount < 0:  # Withdrawal is negative
                        expected_balance = txn.balance_after
                        actual_balance = account.balance
                        
                        # If balance doesn't match, restore it
                        if abs(actual_balance - expected_balance) > Decimal('0.01'):
                            if auto_fix:
                                # Restore balance
                                account.balance = expected_balance
                                account.save()
                                txn.status = TransactionStatus.FAILED.value
                                txn.description = 'Rolled back stuck withdrawal - balance restored'
                                txn.save()
                                rolled_back_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f'  ✓ Rolled back withdrawal, balance restored')
                                )
                            else:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'  ⚠ Balance mismatch detected. Use --auto-fix to restore.'
                                    )
                                )

                elif txn.transaction_type == TransactionType.TRADE_LOCK.value:
                    # Release locked balance if trade was never opened
                    if auto_fix:
                        account = txn.account
                        locked_amount = abs(txn.amount)
                        account.locked_balance = max(
                            Decimal('0.00'),
                            account.locked_balance - locked_amount
                        )
                        account.save()
                        txn.status = TransactionStatus.CANCELLED.value
                        txn.description = 'Cancelled stuck trade lock - balance released'
                        txn.save()
                        rolled_back_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Released locked balance')
                        )

                elif txn.transaction_type == TransactionType.TRADE_PNL.value:
                    # PnL transactions should be completed or failed
                    # If stuck, mark as failed (trade was likely cancelled)
                    if auto_fix:
                        txn.status = TransactionStatus.FAILED.value
                        txn.description = 'Marked stuck PnL as failed'
                        txn.save()
                        rolled_back_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Marked PnL as failed')
                        )

                else:
                    # Generic rollback
                    if auto_fix:
                        txn.status = TransactionStatus.FAILED.value
                        txn.description = f'Rolled back stuck transaction'
                        txn.save()
                        rolled_back_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✓ Rolled back transaction')
                        )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ✗ Error processing {txn.id}: {str(e)}')
                )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Cleanup Complete ===\n'
                f'Total stuck transactions: {total_stuck}\n'
                f'Rolled back: {rolled_back_count}\n'
                f'Errors: {error_count}\n'
            )
        )

        if not auto_fix and total_stuck > 0:
            self.stdout.write(
                self.style.WARNING(
                    '\n⚠ Use --auto-fix to actually fix stuck transactions'
                )
            )

