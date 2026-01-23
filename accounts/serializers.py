from rest_framework import serializers
from .models import Account, Wallet, Transaction, Deposit, Withdrawal, RiskLimit
from common.enums import *
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from dj_rest_auth.registration.serializers import (
    RegisterSerializer as BaseRegisterSerializer,
)
from dj_rest_auth.serializers import UserDetailsSerializer as BaseUserDetailsSerializer
from allauth.socialaccount.models import SocialAccount

User = get_user_model()
class UserDetailSerializer(BaseUserDetailsSerializer):
    """User detail serializer"""
    google_id = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "is_verified",
            "kyc_status",
            "compliance_mode",
            "google_id",
            "avatar",
            "created_at",
        ]
        read_only_fields = ["id", "email", "is_verified", "created_at"]

    def get_google_id(self, obj):
        social_acc = SocialAccount.objects.filter(user=obj, provider='google').first()
        if social_acc:
            return social_acc.uid
        return None
    
    def get_avatar(self, obj):
        social_acc = SocialAccount.objects.filter(user=obj, provider='google').first()
        if social_acc and 'picture' in social_acc.extra_data:
            return social_acc.extra_data['picture'] # Google profil rasmi linki
        return None


class RegisterSerializer(BaseRegisterSerializer):
    """Custom registration serializer"""

    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    email = serializers.EmailField(required=True)
    password1 = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    def validate_email(self, email):
        email = email.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("This email is already registered")
        return email

    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs

    def get_cleaned_data(self):
        return {
            "email": self.validated_data.get("email", ""),
            "first_name": self.validated_data.get("first_name", ""),
            "last_name": self.validated_data.get("last_name", ""),
            "password1": self.validated_data.get("password1", ""),
        }

    def save(self, request):
        user = User.objects.create_user(
            email=self.validated_data["email"],
            first_name=self.validated_data["first_name"],
            last_name=self.validated_data["last_name"],
            password=self.validated_data["password1"],
        )
        return user


class LoginSerializer(serializers.Serializer):
    """Login serializer"""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class GoogleAuthSerializer(serializers.Serializer):
    """Google OAuth serializer"""

    access_token = serializers.CharField(required=True)


class ChangePasswordSerializer(serializers.Serializer):
    """Change password serializer"""

    old_password = serializers.CharField(required=True, write_only=True)
    new_password1 = serializers.CharField(
        required=True, write_only=True, validators=[validate_password]
    )
    new_password2 = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs["new_password1"] != attrs["new_password2"]:
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return attrs


class AccountSerializer(serializers.ModelSerializer):
    """
    Account serializer with multi-mode support.
    Dynamically adjusts response based on CalmMode (Ultra Calm blurs numbers).
    """
    available_balance = serializers.ReadOnlyField()
    margin_level = serializers.ReadOnlyField()
    is_blurred = serializers.SerializerMethodField()
    display_mode = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            "id",
            "account_number",
            "account_type",
            "status",
            "balance",
            "locked_balance",
            "available_balance",
            "equity",
            "margin_level",
            "max_daily_loss",
            "daily_loss_current",
            "max_leverage",
            "is_shariat_compliant",
            "is_blurred",
            "display_mode",
            "created_at",
        ]
        read_only_fields = ["id", "account_number", "locked_balance", "equity"]

    def get_is_blurred(self, obj):
        """Check if numbers should be blurred based on CalmMode"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        user = request.user
        # Ultra Calm mode + Real account = blur numbers
        is_ultra_calm = user.compliance_mode == ComplianceMode.ULTRA_CALM.value
        is_real_account = obj.account_type == AccountType.REAL.value
        
        return is_ultra_calm and is_real_account

    def get_display_mode(self, obj):
        """Get display mode based on user's CalmMode"""
        request = self.context.get('request')
        if not request or not request.user:
            return 'full'
        
        user = request.user
        if user.compliance_mode == ComplianceMode.ULTRA_CALM.value:
            return 'ultra_calm'  # Blur numbers
        elif user.compliance_mode == ComplianceMode.SHARIAT_COMPLIANT.value:
            return 'semi_calm'  # Full visibility but with Sharia indicators
        else:
            return 'full'  # Standard mode

    def to_representation(self, instance):
        """Override to blur sensitive data in Ultra Calm mode"""
        data = super().to_representation(instance)
        
        if data.get('is_blurred'):
            # Blur financial numbers in Ultra Calm mode
            data['balance'] = '***'
            data['available_balance'] = '***'
            data['locked_balance'] = '***'
            data['equity'] = '***'
            data['max_daily_loss'] = '***' if data.get('max_daily_loss') else None
            data['daily_loss_current'] = '***' if data.get('daily_loss_current') else None
        
        return data


class WalletSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(
        source="account.account_number", read_only=True
    )

    class Meta:
        model = Wallet
        fields = [
            "id",
            "account_number",
            "total_deposits",
            "total_withdrawals",
            "total_profit",
            "total_loss",
            "total_fees_paid",
            "updated_at",
        ]


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "transaction_type",
            "status",
            "amount",
            "balance_before",
            "balance_after",
            "trade_id",
            "description",
            "created_at",
            "completed_at",
        ]


class DepositRequestSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(
        choices=[(m.value, m.name) for m in PaymentMethod]
    )
    amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("10.0")
    )
    currency = serializers.CharField(default="USD")
    crypto_address = serializers.CharField(required=False, allow_blank=True)


class DepositSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(
        source="account.account_number", read_only=True
    )

    class Meta:
        model = Deposit
        fields = [
            "id",
            "account_number",
            "payment_method",
            "amount",
            "currency",
            "status",
            "gateway_transaction_id",
            "crypto_address",
            "crypto_txid",
            "created_at",
            "completed_at",
        ]


class WithdrawalRequestSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
    payment_method = serializers.ChoiceField(
        choices=[(m.value, m.name) for m in PaymentMethod]
    )
    amount = serializers.DecimalField(
        max_digits=18, decimal_places=2, min_value=Decimal("10.0")
    )
    currency = serializers.CharField(default="USD")
    destination_address = serializers.CharField()
    destination_details = serializers.JSONField(required=False)


class WithdrawalSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(
        source="account.account_number", read_only=True
    )

    class Meta:
        model = Withdrawal
        fields = [
            "id",
            "account_number",
            "payment_method",
            "amount",
            "fee",
            "net_amount",
            "currency",
            "destination_address",
            "status",
            "rejection_reason",
            "created_at",
            "completed_at",
        ]


class RiskLimitSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskLimit
        fields = "__all__"
