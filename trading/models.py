from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from common.enums import AccountType, TradeEvent

User = get_user_model()


class TradeAccount(models.Model):
    ACCOUNT_TYPE = (
        ('demo', 'Demo'),
        ('real', 'Real'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE)

    balance = models.DecimalField(max_digits=20, decimal_places=2)
    equity = models.DecimalField(max_digits=20, decimal_places=2)

    max_risk_per_trade = models.FloatField(default=2.0)   # % (halol limit)
    max_daily_loss = models.FloatField(default=5.0)       # %

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "trading_tradeaccount"

    def __str__(self):
        return f"{self.user.username} - {self.account_type}"


class Instrument(models.Model):
    symbol = models.CharField(max_length=20, unique=True)

    is_halal = models.BooleanField(default=True)
    is_crypto = models.BooleanField(default=False)

    min_stop_distance = models.DecimalField(
        max_digits=10, decimal_places=6, default=0.0001
    )

    class Meta:
        db_table = "trading_instrument"

    def __str__(self):
        return self.symbol


class Position(models.Model):

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"
        PARTIAL = "PARTIAL", "Partial"

    class Side(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    class Mode(models.TextChoices):
        ULTRA = "ULTRA", "Ultra Calm"
        SEMI = "SEMI", "Semi Calm"

    account = models.ForeignKey(
        TradeAccount, on_delete=models.CASCADE, related_name="positions"
    )
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE)

    side = models.CharField(max_length=4, choices=Side.choices)
    mode = models.CharField(max_length=5, choices=Mode.choices)

    entry_price = models.DecimalField(max_digits=20, decimal_places=6)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=6)
    take_profit = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    risk_percent = models.FloatField()
    position_size = models.DecimalField(max_digits=20, decimal_places=4)
    remaining_size = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN
    )

    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    pnl = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )
    unrealized_pnl = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )

    timeframe = models.CharField(max_length=5, null=True, blank=True)  # M1, M5, H1, D1, etc.
    
    # Hedge-free logic (default disabled)
    hedge_disabled = models.BooleanField(
        default=True,
        help_text="If True, prevents opposite positions (hedging) for same instrument"
    )

    class Meta:
        db_table = "trading_position"

    def __str__(self):
        return f"{self.instrument.symbol} {self.side} ({self.status})"


class PositionLog(models.Model):
    """
    Trade lifecycle event log.
    Stores all trade events (OPEN, CLOSE, SL_HIT, TP_HIT, PARTIAL).
    """
    
    position = models.ForeignKey(
        Position, on_delete=models.CASCADE, related_name="logs"
    )
    event_type = models.CharField(
        max_length=20,
        choices=TradeEvent.choices()
    )
    
    # Event data
    price = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True
    )  # Price at event (entry, close, SL, TP)
    size = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True
    )  # Size affected (for partial close)
    pnl = models.DecimalField(
        max_digits=20, decimal_places=2, null=True, blank=True
    )  # PnL at this event
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)  # Additional event data
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "trading_positionlog"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["position", "-created_at"]),
            models.Index(fields=["event_type"]),
        ]
    
    def __str__(self):
        return f"{self.position.instrument.symbol} {self.event_type} @ {self.created_at}"
