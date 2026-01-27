from django.urls import path
from .api import candles, price, webhooks
from .views import market_prices_view

urlpatterns = [
    path("candles/", candles.CandlestickAPIView.as_view(), name="market-candles"),
    path("price/", price.MarketPriceAPIView.as_view(), name="market-price"),
    path("prices/", price.MarketPricesBulkAPIView.as_view(), name="market-prices-bulk"),
    path("webhooks/price/", webhooks.FlutterPriceWebhookView.as_view(), name="flutter-price-webhook"),
    path("webhooks/trade-event/", webhooks.FlutterTradeEventWebhookView.as_view(), name="flutter-trade-event-webhook"),
    path("", market_prices_view, name="market-prices-page"),  # HTML frontend
]
