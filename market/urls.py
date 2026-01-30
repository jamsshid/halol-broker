from django.urls import path
from .api import candles, price, webhooks

urlpatterns = [
    path("", price.MarketPriceAPIView.as_view(), name="market-price"),
    path("candles/", candles.CandlestickAPIView.as_view(), name="market-candles"),
    path("prices/", price.MarketPricesBulkAPIView.as_view(), name="market-prices-bulk"),
    path("webhooks/price/", webhooks.FlutterPriceWebhookView.as_view(), name="flutter-price-webhook"),
    path("webhooks/trade-event/", webhooks.FlutterTradeEventWebhookView.as_view(), name="flutter-trade-event-webhook"),
]
