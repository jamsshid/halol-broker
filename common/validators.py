from django.core.exceptions import ValidationError
from decimal import Decimal


def validate_positive_decimal(value: Decimal):
    """Validate that decimal is positive"""
    if value <= 0:
        raise ValidationError(
            f"{value} must be positive",
            params={"value": value},
        )


def validate_leverage(value: int):
    """Validate leverage value"""
    valid_leverages = [1, 2, 5, 10, 20, 50, 100, 200, 500]
    if value not in valid_leverages:
        raise ValidationError(
            f"{value} is not a valid leverage. Choose from {valid_leverages}",
            params={"value": value},
        )


def validate_lot_size(value: Decimal):
    """Validate lot size"""
    if value <= 0:
        raise ValidationError("Lot size must be positive")
    if value > Decimal("100.0"):
        raise ValidationError("Lot size cannot exceed 100")
    # Check if it's in 0.01 increments
    if (value * 100) % 1 != 0:
        raise ValidationError("Lot size must be in 0.01 increments")
