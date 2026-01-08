from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from decimal import Decimal
from common.enums import *
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _



class UserManager(BaseUserManager):
    """Custom user manager"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Extended User Model"""
    
    phone = models.CharField(max_length=20, blank=True)
    is_verified = models.BooleanField(default=False)
    kyc_status = models.CharField(max_length=20, default="pending")
    compliance_mode = models.CharField(
        max_length=20,
        choices=[(m.value, m.name) for m in ComplianceMode],
        default=ComplianceMode.STANDARD.value,
    )
    preferred_language = models.CharField(max_length=5, default="en")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "users"


class Account(models.Model):
    """Trading Account (Demo/Real)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="accounts")
    account_type = models.CharField(
        max_length=10, choices=[(t.value, t.name) for t in AccountType]
    )
    account_number = models.CharField(max_length=20, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.name) for s in AccountStatus],
        default=AccountStatus.PENDING_KYC.value,
    )

    # Balance fields
    balance = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    locked_balance = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    equity = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )

    # Risk management
    max_daily_loss = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    daily_loss_current = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    daily_loss_reset_date = models.DateField(auto_now_add=True)
    max_leverage = models.IntegerField(default=100)

    # Compliance
    is_shariat_compliant = models.BooleanField(default=False)
    swap_free = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts"
        unique_together = ["user", "account_type"]

    def __str__(self):
        return f"{self.account_number} ({self.account_type})"

    @property
    def available_balance(self):
        return self.balance - self.locked_balance

    @property
    def margin_level(self):
        if self.locked_balance == 0:
            return Decimal("999999.99")
        return (self.equity / self.locked_balance) * 100


class Wallet(models.Model):
    """Wallet for tracking all balance operations"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.OneToOneField(
        Account, on_delete=models.CASCADE, related_name="wallet"
    )

    # Lifetime stats
    total_deposits = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    total_withdrawals = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    total_profit = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    total_loss = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )
    total_fees_paid = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("0.00")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wallets"


class Transaction(models.Model):
    """All wallet transactions"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_type = models.CharField(
        max_length=20, choices=[(t.value, t.name) for t in TransactionType]
    )
    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.name) for s in TransactionStatus],
        default=TransactionStatus.PENDING.value,
    )

    amount = models.DecimalField(max_digits=18, decimal_places=2)
    balance_before = models.DecimalField(max_digits=18, decimal_places=2)
    balance_after = models.DecimalField(max_digits=18, decimal_places=2)

    # Reference to external entities
    trade_id = models.UUIDField(null=True, blank=True)  # Link to Backend 1 trade
    payment_id = models.CharField(max_length=100, null=True, blank=True)

    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["trade_id"]),
        ]


class Deposit(models.Model):
    """Deposit operations"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="deposits"
    )
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE)

    payment_method = models.CharField(
        max_length=20, choices=[(m.value, m.name) for m in PaymentMethod]
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Payment gateway references
    gateway_transaction_id = models.CharField(max_length=200, blank=True)
    gateway_response = models.JSONField(default=dict)

    # Crypto specific
    crypto_address = models.CharField(max_length=200, blank=True)
    crypto_txid = models.CharField(max_length=200, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.name) for s in TransactionStatus],
        default=TransactionStatus.PENDING.value,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "deposits"
        ordering = ["-created_at"]


class Withdrawal(models.Model):
    """Withdrawal operations"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="withdrawals"
    )
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE)

    payment_method = models.CharField(
        max_length=20, choices=[(m.value, m.name) for m in PaymentMethod]
    )
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    fee = models.DecimalField(max_digits=18, decimal_places=2)
    net_amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")

    # Destination
    destination_address = models.CharField(
        max_length=200
    )  # Bank account, crypto wallet
    destination_details = models.JSONField(default=dict)

    # Payment gateway
    gateway_transaction_id = models.CharField(max_length=200, blank=True)
    gateway_response = models.JSONField(default=dict)

    status = models.CharField(
        max_length=20,
        choices=[(s.value, s.name) for s in TransactionStatus],
        default=TransactionStatus.PENDING.value,
    )

    # Admin approval
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="approved_withdrawals"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "withdrawals"
        ordering = ["-created_at"]


class RiskLimit(models.Model):
    """User-specific risk limits"""

    account = models.OneToOneField(
        Account, on_delete=models.CASCADE, related_name="risk_limits"
    )

    # Override defaults
    max_leverage = models.IntegerField(default=100)
    max_daily_loss_amount = models.DecimalField(
        max_digits=18, decimal_places=2, null=True
    )
    max_daily_loss_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.0")
    )
    max_position_size_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("20.0")
    )

    # Trading limits
    max_open_positions = models.IntegerField(default=10)
    max_lot_size = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("100.0")
    )

    # Shariat compliance limits
    max_overnight_exposure_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True
    )
    forbidden_instruments = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "risk_limits"
