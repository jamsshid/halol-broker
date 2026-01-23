"""
Trading API Serializers
DRF serializers for trading endpoints.
"""
from rest_framework import serializers
from decimal import Decimal
from trading.models import Position, PositionLog, TradeAccount, Instrument
from common.enums import TradeEvent


class InstrumentSerializer(serializers.ModelSerializer):
    """Instrument serializer"""
    
    class Meta:
        model = Instrument
        fields = ['id', 'symbol', 'is_halal', 'is_crypto', 'min_stop_distance']


class PositionLogSerializer(serializers.ModelSerializer):
    """Position log serializer"""
    
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)
    
    class Meta:
        model = PositionLog
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'price',
            'size',
            'pnl',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PositionSerializer(serializers.ModelSerializer):
    """Position serializer"""
    
    instrument = InstrumentSerializer(read_only=True)
    instrument_symbol = serializers.CharField(write_only=True, required=False)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    side_display = serializers.CharField(source='get_side_display', read_only=True)
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)
    logs = PositionLogSerializer(many=True, read_only=True)
    
    class Meta:
        model = Position
        fields = [
            'id',
            'account',
            'instrument',
            'instrument_symbol',
            'side',
            'side_display',
            'mode',
            'mode_display',
            'entry_price',
            'stop_loss',
            'take_profit',
            'risk_percent',
            'position_size',
            'remaining_size',
            'status',
            'status_display',
            'opened_at',
            'closed_at',
            'pnl',
            'unrealized_pnl',
            'timeframe',
            'logs',
        ]
        read_only_fields = [
            'id',
            'opened_at',
            'closed_at',
            'pnl',
            'unrealized_pnl',
            'status',
        ]


class TradeOpenRequestSerializer(serializers.Serializer):
    """Trade open request serializer"""
    
    account_id = serializers.IntegerField(required=True, help_text="TradeAccount ID")
    symbol = serializers.CharField(required=True, max_length=20, help_text="Instrument symbol (e.g., EURUSD, BTCUSD)")
    side = serializers.ChoiceField(
        choices=[Position.Side.BUY, Position.Side.SELL],
        required=True,
        help_text="Trade direction: BUY or SELL"
    )
    mode = serializers.ChoiceField(
        choices=[Position.Mode.ULTRA, Position.Mode.SEMI],
        required=True,
        help_text="Calm mode: ULTRA or SEMI"
    )
    entry_price = serializers.DecimalField(
        required=True,
        max_digits=20,
        decimal_places=6,
        help_text="Entry price"
    )
    stop_loss = serializers.DecimalField(
        required=True,
        max_digits=20,
        decimal_places=6,
        help_text="Stop loss price (MANDATORY)"
    )
    take_profit = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=20,
        decimal_places=6,
        help_text="Take profit price (OPTIONAL)"
    )
    risk_percent = serializers.FloatField(
        required=True,
        min_value=0.01,
        max_value=10.0,
        help_text="Risk percentage (e.g., 1.0 for 1%)"
    )
    timeframe = serializers.ChoiceField(
        choices=[
            ('M1', 'M1'), ('M5', 'M5'), ('M15', 'M15'), ('M30', 'M30'),
            ('H1', 'H1'), ('H4', 'H4'), ('D1', 'D1'), ('W1', 'W1'), ('MN1', 'MN1')
        ],
        required=False,
        allow_null=True,
        help_text="Timeframe (OPTIONAL)"
    )
    
    def validate(self, attrs):
        """Validate trade parameters"""
        entry_price = attrs.get('entry_price')
        stop_loss = attrs.get('stop_loss')
        take_profit = attrs.get('take_profit')
        side = attrs.get('side')
        
        # Validate stop loss direction
        if side == Position.Side.BUY and stop_loss >= entry_price:
            raise serializers.ValidationError({
                'stop_loss': 'For BUY, stop loss must be below entry price'
            })
        if side == Position.Side.SELL and stop_loss <= entry_price:
            raise serializers.ValidationError({
                'stop_loss': 'For SELL, stop loss must be above entry price'
            })
        
        # Validate take profit if provided
        if take_profit is not None:
            if side == Position.Side.BUY and take_profit <= entry_price:
                raise serializers.ValidationError({
                    'take_profit': 'For BUY, take profit must be above entry price'
                })
            if side == Position.Side.SELL and take_profit >= entry_price:
                raise serializers.ValidationError({
                    'take_profit': 'For SELL, take profit must be below entry price'
                })
        
        return attrs


class TradeOpenResponseSerializer(serializers.Serializer):
    """Trade open response serializer"""
    
    position_id = serializers.IntegerField()
    symbol = serializers.CharField()
    side = serializers.CharField()
    mode = serializers.CharField()
    entry_price = serializers.DecimalField(max_digits=20, decimal_places=6)
    stop_loss = serializers.DecimalField(max_digits=20, decimal_places=6)
    take_profit = serializers.DecimalField(max_digits=20, decimal_places=6, allow_null=True)
    position_size = serializers.DecimalField(max_digits=20, decimal_places=4)
    status = serializers.CharField()
    timeframe = serializers.CharField(allow_null=True)


class TradeCloseRequestSerializer(serializers.Serializer):
    """Trade close request serializer"""
    
    position_id = serializers.IntegerField(required=True, help_text="Position ID to close")
    closing_price = serializers.DecimalField(
        required=True,
        max_digits=20,
        decimal_places=6,
        help_text="Closing price"
    )
    close_size = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=20,
        decimal_places=4,
        help_text="Size to close (OPTIONAL - if not provided, full close)"
    )


class TradeCloseResponseSerializer(serializers.Serializer):
    """Trade close response serializer"""
    
    position_id = serializers.IntegerField()
    status = serializers.CharField()
    pnl = serializers.DecimalField(max_digits=20, decimal_places=2)
    closing_price = serializers.DecimalField(max_digits=20, decimal_places=6)
    remaining_size = serializers.DecimalField(max_digits=20, decimal_places=4)
