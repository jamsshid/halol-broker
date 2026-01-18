from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import date

from ..models import Account, Notification, NotificationLevel
from common.enums import TransactionStatus


class AlertService:
    """Risk monitoring and notification service"""

    RISK_THRESHOLD_PERCENT = Decimal("85.00")  # 85% of max_daily_loss triggers alert

    @staticmethod
    @transaction.atomic
    def check_and_create_risk_alert(account_id):
        """
        Check if account's daily_loss_current has reached 85% of max_daily_loss.
        If yes, create a WARNING notification. If 100% or more, create CRITICAL.
        """
        try:
            account = Account.objects.select_for_update().get(id=account_id)
        except Account.DoesNotExist:
            return None


        if account.daily_loss_reset_date < date.today():
            account.daily_loss_current = Decimal("0.00")
            account.daily_loss_reset_date = date.today()
            account.save()

        # Check if max_daily_loss is set
        if not account.max_daily_loss or account.max_daily_loss <= 0:
            return None

        # Calculate threshold (85% of max_daily_loss)
        threshold_85 = account.max_daily_loss * (AlertService.RISK_THRESHOLD_PERCENT / Decimal("100.00"))

        # Calculate current loss percentage
        loss_percentage = (account.daily_loss_current / account.max_daily_loss) * Decimal("100.00")

        # Check if we should create a notification
        notification = None

        if account.daily_loss_current >= account.max_daily_loss:
            # CRITICAL: Loss limit exceeded or reached
            notification = Notification.objects.create(
                user=account.user,
                account=account,
                message=(
                    f"CRITICAL: Daily loss limit reached! "
                    f"Current loss: {account.daily_loss_current} USD "
                    f"({loss_percentage.quantize(Decimal('0.01'))}% of limit: {account.max_daily_loss} USD). "
                    f"Trading may be restricted."
                ),
                level=NotificationLevel.CRITICAL,
                metadata={
                    "daily_loss_current": str(account.daily_loss_current),
                    "max_daily_loss": str(account.max_daily_loss),
                    "loss_percentage": str(loss_percentage.quantize(Decimal("0.01"))),
                    "account_number": account.account_number,
                },
            )

        elif account.daily_loss_current >= threshold_85:
            # WARNING: Approaching loss limit
            # Check if we already created a notification today for this threshold
            today = timezone.now().date()
            existing_notification = Notification.objects.filter(
                user=account.user,
                account=account,
                level=NotificationLevel.WARNING,
                created_at__date=today,
                metadata__daily_loss_current__gte=str(threshold_85),
            ).first()

            if not existing_notification:
                notification = Notification.objects.create(
                    user=account.user,
                    account=account,
                    message=(
                        f"WARNING: Daily loss approaching limit! "
                        f"Current loss: {account.daily_loss_current} USD "
                        f"({loss_percentage.quantize(Decimal('0.01'))}% of limit: {account.max_daily_loss} USD). "
                        f"Consider reducing risk exposure."
                    ),
                    level=NotificationLevel.WARNING,
                    metadata={
                        "daily_loss_current": str(account.daily_loss_current),
                        "max_daily_loss": str(account.max_daily_loss),
                        "loss_percentage": str(loss_percentage.quantize(Decimal("0.01"))),
                        "account_number": account.account_number,
                        "threshold_percent": str(AlertService.RISK_THRESHOLD_PERCENT),
                    },
                )

        return notification

    @staticmethod
    def get_user_notifications(user_id, unread_only=False, limit=None):
        """Get notifications for a user"""
        queryset = Notification.objects.filter(user_id=user_id)

        if unread_only:
            queryset = queryset.filter(is_read=False)

        queryset = queryset.order_by("-created_at")

        if limit:
            queryset = queryset[:limit]

        return queryset

    @staticmethod
    @transaction.atomic
    def mark_notification_as_read(notification_id, user_id):
        """Mark a notification as read"""
        try:
            notification = Notification.objects.get(id=notification_id, user_id=user_id)
            notification.is_read = True
            notification.save()
            return notification
        except Notification.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def mark_all_as_read(user_id, account_id=None):
        """Mark all notifications as read for a user (optionally filtered by account)"""
        queryset = Notification.objects.filter(user_id=user_id, is_read=False)
        
        if account_id:
            queryset = queryset.filter(account_id=account_id)

        count = queryset.update(is_read=True)
        return count

