"""
Django Signals for real-time updates via WebSocket/Signal
Used for Flutter app real-time PnL updates
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging

from .models import Transaction, Account
from common.enums import TransactionType

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


@receiver(post_save, sender=Transaction)
def notify_pnl_update(sender, instance, created, **kwargs):
    """
    Send real-time PnL update via WebSocket when trade PnL transaction is completed.
    Used by Flutter app for live updates.
    """
    # Only notify for completed PnL transactions
    if (
        instance.transaction_type == TransactionType.TRADE_PNL.value
        and instance.status == 'completed'
        and channel_layer
    ):
        try:
            account = instance.account
            user_id = str(account.user_id)
            
            # Prepare update payload
            payload = {
                'type': 'pnl_update',
                'transaction_id': str(instance.id),
                'account_id': str(account.id),
                'account_number': account.account_number,
                'pnl_amount': str(instance.amount),
                'balance_before': str(instance.balance_before),
                'balance_after': str(instance.balance_after),
                'new_balance': str(account.balance),
                'available_balance': str(account.available_balance),
                'trade_id': str(instance.trade_id) if instance.trade_id else None,
                'timestamp': instance.completed_at.isoformat() if instance.completed_at else None,
            }
            
            # Send to user's personal channel group
            group_name = f"user_{user_id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'pnl_update',
                    'message': payload
                }
            )
            
            logger.info(
                f"Sent PnL update to user {user_id} for transaction {instance.id}"
            )
        except Exception as e:
            logger.error(
                f"Error sending PnL update: {str(e)}",
                exc_info=True
            )


@receiver(post_save, sender=Account)
def notify_balance_update(sender, instance, **kwargs):
    """
    Send real-time balance update when account balance changes.
    """
    if channel_layer:
        try:
            user_id = str(instance.user_id)
            group_name = f"user_{user_id}"
            
            payload = {
                'type': 'balance_update',
                'account_id': str(instance.id),
                'account_number': instance.account_number,
                'balance': str(instance.balance),
                'available_balance': str(instance.available_balance),
                'locked_balance': str(instance.locked_balance),
                'equity': str(instance.equity),
            }
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'balance_update',
                    'message': payload
                }
            )
        except Exception as e:
            logger.error(
                f"Error sending balance update: {str(e)}",
                exc_info=True
            )

