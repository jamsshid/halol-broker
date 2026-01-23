from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for AuditLog model"""
    list_display = [
        'audit_type',
        'severity',
        'account_number',
        'is_consistent',
        'difference',
        'created_at'
    ]
    list_filter = ['audit_type', 'severity', 'is_consistent', 'created_at']
    search_fields = ['account_number', 'message']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Audit Information', {
            'fields': ('id', 'audit_type', 'severity', 'is_consistent')
        }),
        ('Account Details', {
            'fields': ('account_id', 'account_number')
        }),
        ('Results', {
            'fields': ('expected_value', 'actual_value', 'difference')
        }),
        ('Details', {
            'fields': ('message', 'details')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at')
        }),
    )
