# from django.db import models
# from django.contrib.auth.models import User


# class TradeAccount(models.Model):
#     ACCOUNT_TYPE = (
#         ('demo', 'Demo'),
#         ('real', 'Real'),
#     )

#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE)

#     balance = models.DecimalField(max_digits=20, decimal_places=2)
#     equity = models.DecimalField(max_digits=20, decimal_places=2)

#     max_risk_per_trade = models.FloatField(default=2.0)   # % (halol limit)
#     max_daily_loss = models.FloatField(default=5.0)       # %

#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user.username} - {self.account_type}"



# class Instrument(models.Model):
#     symbol = models.CharField(max_length=20, unique=True)

#     is_halal = models.BooleanField(default=True)
#     is_crypto = models.BooleanField(default=False)

#     min_stop_distance = models.DecimalField(
#         max_digits=10, decimal_places=6, default=0.0001
#     )

#     def __str__(self):
#         return self.symbol



# class Position(models.Model):

#     class Status(models.TextChoices):
#         OPEN = "OPEN", "Open"
#         CLOSED = "CLOSED", "Closed"

#     class Side(models.TextChoices):
#         BUY = "BUY", "Buy"
#         SELL = "SELL", "Sell"

#     class Mode(models.TextChoices):
#         ULTRA = "ULTRA", "Ultra Calm"
#         SEMI = "SEMI", "Semi Calm"

#     account = models.ForeignKey(
#         TradeAccount, on_delete=models.CASCADE, related_name="positions"
#     )
#     instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE)

#     side = models.CharField(max_length=4, choices=Side.choices)
#     mode = models.CharField(max_length=5, choices=Mode.choices)

#     entry_price = models.DecimalField(max_digits=20, decimal_places=6)
#     stop_loss = models.DecimalField(max_digits=20, decimal_places=6)
#     take_profit = models.DecimalField(max_digits=20, decimal_places=6)

#     risk_percent = models.FloatField()
#     position_size = models.DecimalField(max_digits=20, decimal_places=4)

#     status = models.CharField(
#         max_length=10,
#         choices=Status.choices,
#         default=Status.OPEN
#     )

#     opened_at = models.DateTimeField(auto_now_add=True)
#     closed_at = models.DateTimeField(null=True, blank=True)

#     pnl = models.DecimalField(
#         max_digits=20, decimal_places=2, null=True, blank=True
#     )

#     def __str__(self):
#         return f"{self.instrument.symbol} {self.side} ({self.status})"
