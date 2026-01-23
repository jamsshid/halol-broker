from django.urls import path
from .api import candles

urlpatterns = [
    path("candles/", candles.CandlestickAPIView.as_view(), name="market-candles"),
]
