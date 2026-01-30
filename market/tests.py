from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal

class MarketPriceAPITest(APITestCase):
    """Test market price POST API"""
    
    def test_set_market_price_valid(self):
        """Test setting a valid market price"""
        data = {
            "symbol": "EURUSD",
            "bid": "1.0500",
            "ask": "1.0505",
            "mode": "demo",
            "source": "test"
        }
        response = self.client.post('/api/market/price/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
    
    def test_set_market_price_invalid_bid_ask(self):
        """Test invalid bid >= ask"""
        data = {
            "symbol": "EURUSD",
            "bid": "1.0505",
            "ask": "1.0500",
            "mode": "demo"
        }
        response = self.client.post('/api/market/price/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_set_market_price_invalid_symbol(self):
        """Test invalid symbol not uppercase"""
        data = {
            "symbol": "eurusd",
            "bid": "1.0500",
            "ask": "1.0505",
            "mode": "demo"
        }
        response = self.client.post('/api/market/price/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
