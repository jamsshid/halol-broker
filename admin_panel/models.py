from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid

User = get_user_model()


class AuditLog(models.Model):
    """
    Audit log for storing wallet consistency audit results.
    Used to track data integrity checks and critical discrepancies.
    """
    
    AUDIT_TYPE_CHOICES = [
        ('wallet_consistency', 'Wallet Consistency'),
        ('transaction_integrity', 'Transaction Integrity'),
        ('balance_verification', 'Balance Verification'),
        ('sharia_compliance', 'Sharia Compliance'),
    ]
    
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    audit_type = models.CharField(max_length=50, choices=AUDIT_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='info')
    
    # Account reference (nullable for system-wide audits)
    account_id = models.UUIDField(null=True, blank=True, db_index=True)
    account_number = models.CharField(max_length=20, blank=True)
    
    # Audit results
    is_consistent = models.BooleanField(default=True)
    expected_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    actual_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    
    # Details
    message = models.TextField()
    details = models.JSONField(default=dict)
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["audit_type", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
            models.Index(fields=["account_id", "-created_at"]),
            models.Index(fields=["is_consistent", "-created_at"]),
        ]
    
    def __str__(self):
        return f"{self.audit_type} - {self.severity} - {self.created_at}"
