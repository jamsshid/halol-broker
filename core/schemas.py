"""
API Schemas for drf-spectacular
Custom schema definitions for OpenAPI documentation.
"""
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

# Import all serializers
from accounts.serializers import *
from trading.serializers import *
from market.serializers import *
from common.serializers import *

# Define custom schemas for enums
ACCOUNT_STATUS_ENUM = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "enum": [s.value for s in AccountStatus]},
        "name": {"type": "string"}
    }
}

ACCOUNT_TYPE_ENUM = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "enum": [t.value for t in AccountType]},
        "name": {"type": "string"}
    }
}

PAYMENT_METHOD_ENUM = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "enum": [m.value for m in PaymentMethod]},
        "name": {"type": "string"}
    }
}

TRANSACTION_TYPE_ENUM = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "enum": [t.value for t in TransactionType]},
        "name": {"type": "string"}
    }
}

SIDE_ENUM = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "enum": ["BUY", "SELL"]},
        "name": {"type": "string"}
    }
}

TIMEFRAME_ENUM = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "enum": Timeframe.all_values()},
        "name": {"type": "string"}
    }
}

MODE_ENUM = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "enum": ["ULTRA", "SEMI"]},
        "name": {"type": "string"}
    }
}

TRANSACTION_STATUS_ENUM = {
    "type": "object",
    "properties": {
        "value": {"type": "string", "enum": [s.value for s in TransactionStatus]},
        "name": {"type": "string"}
    }
}

# Schema definitions
ACCOUNT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "account_number": {"type": "string"},
        "account_type": {"type": "string", "enum": [t.value for t in AccountType]},
        "status": {"type": "string", "enum": [s.value for s in AccountStatus]},
        "balance": {"type": "string", "format": "decimal"},
        "locked_balance": {"type": "string", "format": "decimal"},
        "available_balance": {"type": "string", "format": "decimal"},
        "equity": {"type": "string", "format": "decimal"},
        "margin_level": {"type": "string", "format": "decimal"},
        "max_daily_loss": {"type": "string", "format": "decimal", "nullable": True},
        "daily_loss_current": {"type": "string", "format": "decimal"},
        "max_leverage": {"type": "integer"},
        "is_shariat_compliant": {"type": "boolean"},
        "created_at": {"type": "string", "format": "date-time"},
    }
}

CANDLESTICK_SCHEMA = {
    "type": "object",
    "properties": {
        "time": {"type": "string", "format": "date-time"},
        "open": {"type": "string", "format": "decimal"},
        "high": {"type": "string", "format": "decimal"},
        "low": {"type": "string", "format": "decimal"},
        "close": {"type": "string", "format": "decimal"},
        "volume": {"type": "string", "format": "decimal"},
    }
}

CANDLESTICK_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "timeframe": {"type": "string", "enum": Timeframe.all_values()},
        "count": {"type": "integer"},
        "candles": {
            "type": "array",
            "items": CANDLESTICK_SCHEMA
        }
    }
}

DEPOSIT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "account_number": {"type": "string"},
        "payment_method": {"type": "string", "enum": [m.value for m in PaymentMethod]},
        "amount": {"type": "string", "format": "decimal"},
        "currency": {"type": "string"},
        "status": {"type": "string", "enum": [s.value for s in TransactionStatus]},
        "gateway_transaction_id": {"type": "string"},
        "crypto_address": {"type": "string"},
        "crypto_txid": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "completed_at": {"type": "string", "format": "date-time", "nullable": True},
    }
}

TRANSACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "transaction_type": {"type": "string", "enum": [t.value for t in TransactionType]},
        "status": {"type": "string", "enum": [s.value for s in TransactionStatus]},
        "amount": {"type": "string", "format": "decimal"},
        "balance_before": {"type": "string", "format": "decimal"},
        "balance_after": {"type": "string", "format": "decimal"},
        "trade_id": {"type": "string", "format": "uuid", "nullable": True},
        "description": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "completed_at": {"type": "string", "format": "date-time", "nullable": True},
    }
}

WITHDRAWAL_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "format": "uuid"},
        "account_number": {"type": "string"},
        "payment_method": {"type": "string", "enum": [m.value for m in PaymentMethod]},
        "amount": {"type": "string", "format": "decimal"},
        "fee": {"type": "string", "format": "decimal"},
        "net_amount": {"type": "string", "format": "decimal"},
        "currency": {"type": "string"},
        "destination_address": {"type": "string"},
        "status": {"type": "string", "enum": [s.value for s in TransactionStatus]},
        "rejection_reason": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"},
        "completed_at": {"type": "string", "format": "date-time", "nullable": True},
    }
}

TRADE_OPEN_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "account_id": {"type": "integer"},
        "symbol": {"type": "string"},
        "side": {"type": "string", "enum": ["BUY", "SELL"]},
        "mode": {"type": "string", "enum": ["ULTRA", "SEMI"]},
        "entry_price": {"type": "string", "format": "decimal"},
        "stop_loss": {"type": "string", "format": "decimal"},
        "take_profit": {"type": "string", "format": "decimal", "nullable": True},
        "risk_percent": {"type": "number", "format": "float"},
        "timeframe": {"type": "string", "enum": Timeframe.all_values(), "nullable": True},
    },
    "required": ["account_id", "symbol", "side", "mode", "entry_price", "stop_loss", "risk_percent"]
}

TRADE_OPEN_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "position_id": {"type": "integer"},
        "symbol": {"type": "string"},
        "side": {"type": "string"},
        "mode": {"type": "string"},
        "entry_price": {"type": "string", "format": "decimal"},
        "stop_loss": {"type": "string", "format": "decimal"},
        "take_profit": {"type": "string", "format": "decimal", "nullable": True},
        "position_size": {"type": "string", "format": "decimal"},
        "status": {"type": "string"},
        "timeframe": {"type": "string", "nullable": True},
    }
}

TRADE_CLOSE_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "position_id": {"type": "integer"},
        "closing_price": {"type": "string", "format": "decimal"},
        "close_size": {"type": "string", "format": "decimal", "nullable": True},
    },
    "required": ["position_id", "closing_price"]
}

TRADE_CLOSE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "position_id": {"type": "integer"},
        "status": {"type": "string"},
        "pnl": {"type": "string", "format": "decimal"},
        "closing_price": {"type": "string", "format": "decimal"},
        "remaining_size": {"type": "string", "format": "decimal"},
    }
}

TOKEN_REFRESH_SCHEMA = {
    "type": "object",
    "properties": {
        "refresh": {"type": "string"},
    },
    "required": ["refresh"]
}

# Paginated schemas
PAGINATED_ACCOUNT_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "next": {"type": "string", "format": "uri", "nullable": True},
        "previous": {"type": "string", "format": "uri", "nullable": True},
        "results": {
            "type": "array",
            "items": ACCOUNT_SCHEMA
        }
    }
}

PAGINATED_DEPOSIT_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "next": {"type": "string", "format": "uri", "nullable": True},
        "previous": {"type": "string", "format": "uri", "nullable": True},
        "results": {
            "type": "array",
            "items": DEPOSIT_SCHEMA
        }
    }
}

PAGINATED_TRANSACTION_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "next": {"type": "string", "format": "uri", "nullable": True},
        "previous": {"type": "string", "format": "uri", "nullable": True},
        "results": {
            "type": "array",
            "items": TRANSACTION_SCHEMA
        }
    }
}

PAGINATED_WITHDRAWAL_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "count": {"type": "integer"},
        "next": {"type": "string", "format": "uri", "nullable": True},
        "previous": {"type": "string", "format": "uri", "nullable": True},
        "results": {
            "type": "array",
            "items": WITHDRAWAL_SCHEMA
        }
    }
}

# Patched schemas (for partial updates)
PATCHED_ACCOUNT_SCHEMA = {
    "type": "object",
    "properties": {
        "account_type": {"type": "string", "enum": [t.value for t in AccountType]},
        "status": {"type": "string", "enum": [s.value for s in AccountStatus]},
        "balance": {"type": "string", "format": "decimal"},
        "max_daily_loss": {"type": "string", "format": "decimal", "nullable": True},
        "max_leverage": {"type": "integer"},
        "is_shariat_compliant": {"type": "boolean"},
        "swap_free": {"type": "boolean"},
    }
}

PATCHED_DEPOSIT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": [s.value for s in TransactionStatus]},
        "gateway_transaction_id": {"type": "string"},
        "crypto_txid": {"type": "string"},
    }
}

PATCHED_WITHDRAWAL_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": [s.value for s in TransactionStatus]},
        "gateway_transaction_id": {"type": "string"},
        "approved_by": {"type": "integer", "nullable": True},
        "approved_at": {"type": "string", "format": "date-time", "nullable": True},
        "rejection_reason": {"type": "string"},
    }
}