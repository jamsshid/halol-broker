"""
URLs for payment webhook endpoints
"""
from django.urls import path
from .payment_webhook_views import PaymentWebhookView

urlpatterns = [
    path('<str:gateway_name>/', PaymentWebhookView.as_view(), name='payment-webhook'),
]

