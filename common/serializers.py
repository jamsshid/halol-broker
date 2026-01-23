"""
Common Serializers
DRF serializers for common models and enums.
"""
from rest_framework import serializers
from .enums import *


class AccountStatusEnumSerializer(serializers.Serializer):
    """Account status enum serializer"""
    value = serializers.CharField()
    name = serializers.CharField()


class AccountTypeEnumSerializer(serializers.Serializer):
    """Account type enum serializer"""
    value = serializers.CharField()
    name = serializers.CharField()


class PaymentMethodEnumSerializer(serializers.Serializer):
    """Payment method enum serializer"""
    value = serializers.CharField()
    name = serializers.CharField()


class TransactionTypeEnumSerializer(serializers.Serializer):
    """Transaction type enum serializer"""
    value = serializers.CharField()
    name = serializers.CharField()


class SideEnumSerializer(serializers.Serializer):
    """Trade side enum serializer"""
    value = serializers.CharField()
    name = serializers.CharField()


class TimeframeEnumSerializer(serializers.Serializer):
    """Timeframe enum serializer"""
    value = serializers.CharField()
    name = serializers.CharField()


class ModeEnumSerializer(serializers.Serializer):
    """Calm mode enum serializer"""
    value = serializers.CharField()
    name = serializers.CharField()


class Status643EnumSerializer(serializers.Serializer):
    """Transaction status enum serializer"""
    value = serializers.CharField()
    name = serializers.CharField()


class NullEnumSerializer(serializers.Serializer):
    """Null enum placeholder"""
    pass</content>
<parameter name="filePath">/home/xushnudbek/halol-broker/common/serializers.py