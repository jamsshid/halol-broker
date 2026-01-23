"""
Payment Gateway Service - Handles external payment gateway webhooks
"""
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from typing import Dict, Any, Optional
import logging
import hmac
import hashlib
import json

from ..models import Account, Deposit, Transaction
from ..services.deposit_service import DepositService
from common.enums import TransactionStatus
from common.exceptions import PaymentGatewayError, SecurityException

logger = logging.getLogger(__name__)


class PaymentGatewayService:
    """Service for handling payment gateway webhooks and integrations"""

    @staticmethod
    def verify_webhook_signature(
        payload: str,
        signature: str,
        secret_key: str
    ) -> bool:
        """
        Verify webhook signature to ensure request authenticity.
        
        Args:
            payload: Raw request body
            signature: Signature from headers
            secret_key: Secret key for verification
        
        Returns:
            bool: True if signature is valid
        """
        try:
            # Generate expected signature
            expected_signature = hmac.new(
                secret_key.encode('utf-8'),
                payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures (constant-time comparison)
            return hmac.compare_digest(expected_signature, signature)
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {str(e)}")
            return False

    @staticmethod
    @transaction.atomic
    def process_deposit_webhook(
        gateway_name: str,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
        secret_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process deposit webhook from external payment gateway.
        
        Args:
            gateway_name: Name of the payment gateway (e.g., 'stripe', 'paypal')
            payload: Webhook payload
            signature: Webhook signature for verification
            secret_key: Secret key for signature verification
        
        Returns:
            Dict with processing result
        """
        # Verify signature if provided
        if signature and secret_key:
            payload_str = json.dumps(payload, sort_keys=True)
            if not PaymentGatewayService.verify_webhook_signature(
                payload_str, signature, secret_key
            ):
                raise SecurityException(
                    "Invalid webhook signature",
                    details={'gateway': gateway_name}
                )
        
        # Extract transaction details based on gateway
        gateway_transaction_id = payload.get('transaction_id') or payload.get('id')
        amount = Decimal(str(payload.get('amount', 0)))
        currency = payload.get('currency', 'USD')
        status = payload.get('status', 'pending').lower()
        
        # Find deposit by gateway transaction ID
        try:
            deposit = Deposit.objects.get(
                gateway_transaction_id=gateway_transaction_id
            )
        except Deposit.DoesNotExist:
            logger.warning(
                f"Deposit not found for gateway transaction: {gateway_transaction_id}"
            )
            raise PaymentGatewayError(
                f"Deposit not found for transaction {gateway_transaction_id}",
                details={'gateway_transaction_id': gateway_transaction_id}
            )
        
        # Process based on status
        if status in ['completed', 'success', 'paid']:
            # Complete the deposit
            DepositService.complete_deposit(
                deposit_id=deposit.id,
                gateway_transaction_id=gateway_transaction_id,
                gateway_response=payload
            )
            
            logger.info(
                f"Deposit {deposit.id} completed via webhook from {gateway_name}"
            )
            
            return {
                'success': True,
                'deposit_id': str(deposit.id),
                'status': 'completed',
                'message': 'Deposit processed successfully'
            }
        
        elif status in ['failed', 'cancelled', 'rejected']:
            # Mark deposit as failed
            deposit.status = TransactionStatus.FAILED.value
            deposit.gateway_response = payload
            deposit.save()
            
            deposit.transaction.status = TransactionStatus.FAILED.value
            deposit.transaction.save()
            
            logger.info(
                f"Deposit {deposit.id} failed via webhook from {gateway_name}"
            )
            
            return {
                'success': False,
                'deposit_id': str(deposit.id),
                'status': 'failed',
                'message': 'Deposit failed'
            }
        
        else:
            # Pending or unknown status
            logger.info(
                f"Deposit {deposit.id} still pending via webhook from {gateway_name}"
            )
            
            return {
                'success': True,
                'deposit_id': str(deposit.id),
                'status': 'pending',
                'message': 'Deposit still processing'
            }

    @staticmethod
    def create_webhook_endpoint_url(gateway_name: str) -> str:
        """
        Generate webhook endpoint URL for payment gateway.
        
        Args:
            gateway_name: Name of the payment gateway
        
        Returns:
            Webhook URL string
        """
        # In production, this would use settings.BASE_URL
        base_url = "https://api.halol-broker.com"  # Should come from settings
        return f"{base_url}/api/payments/webhooks/{gateway_name}/"

