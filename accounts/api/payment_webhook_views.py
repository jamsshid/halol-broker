"""
Payment Gateway Webhook Views
Handle incoming webhooks from external payment gateways
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import logging

try:
    from ..services.payment_gateway_service import PaymentGatewayService
    from common.exceptions import PaymentGatewayError, SecurityException
except ImportError as e:
    logging.error(f"Error importing payment gateway service: {e}")
    PaymentGatewayService = None
    PaymentGatewayError = Exception
    SecurityException = Exception

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(APIView):
    """
    Generic webhook endpoint for payment gateways.
    CSRF exempt because webhooks come from external services.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Payment Gateway Webhook",
        description="Receive webhooks from payment gateways (Stripe, PayPal, etc.)",
        request={
            'type': 'object',
            'description': 'Webhook payload from payment gateway'
        },
        responses={
            200: OpenApiResponse(description="Webhook processed successfully"),
            400: OpenApiResponse(description="Invalid webhook payload"),
        }
    )
    def post(self, request, gateway_name):
        """
        Process webhook from payment gateway.
        
        POST /api/payments/webhooks/{gateway_name}/
        """
        if PaymentGatewayService is None:
            return Response(
                {'error': 'Payment gateway service not available'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        try:
            # Get signature from headers (gateway-specific)
            signature = request.META.get('HTTP_X_SIGNATURE') or request.META.get('HTTP_X_WEBHOOK_SIGNATURE')
            
            # Get secret key from settings (should be in environment)
            from django.conf import settings
            secret_key = getattr(settings, 'PAYMENT_GATEWAY_SECRETS', {}).get(gateway_name)
            
            # Process webhook
            result = PaymentGatewayService.process_deposit_webhook(
                gateway_name=gateway_name,
                payload=request.data if isinstance(request.data, dict) else json.loads(request.body),
                signature=signature,
                secret_key=secret_key
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except SecurityException as e:
            logger.warning(f"Security error processing webhook: {str(e)}")
            return Response(
                {'error': 'Invalid webhook signature'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except PaymentGatewayError as e:
            logger.error(f"Payment gateway error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error processing webhook: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

