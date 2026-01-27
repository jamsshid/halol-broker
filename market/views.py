"""
Market Views
Simple HTML view for market prices display.
"""
from django.shortcuts import render


def market_prices_view(request):
    """Render market prices HTML page"""
    return render(request, 'market_prices.html')
