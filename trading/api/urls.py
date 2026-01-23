from django.urls import path
from .open import TradeOpenAPIView
from .close import TradeCloseAPIView
from .history import TradeHistoryAPIView, TradeEventsAPIView

urlpatterns = [
    path("open/", TradeOpenAPIView.as_view(), name="trade-open"),
    path("close/", TradeCloseAPIView.as_view(), name="trade-close"),
    path("history/", TradeHistoryAPIView.as_view(), name="trade-history"),
    path("events/", TradeEventsAPIView.as_view(), name="trade-events"),
]
