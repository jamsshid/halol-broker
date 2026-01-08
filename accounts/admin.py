from django.contrib import admin
from .models import User, Account, Wallet, Transaction, Deposit, Withdrawal, RiskLimit
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email",
        "first_name",
        "last_name",
        "is_verified",
        "is_staff",
        "created_at",
    ]
    list_filter = ["is_verified", "is_staff", "is_superuser", "compliance_mode"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["-created_at"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone", "avatar")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "is_verified")},
        ),
        ("Google OAuth", {"fields": ("google_id",)}),
        ("Compliance", {"fields": ("kyc_status", "compliance_mode")}),
        ("Dates", {"fields": ("created_at", "updated_at", "last_login_at")}),
    )

    readonly_fields = ["created_at", "updated_at", "last_login"]

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


# admin.site.register(User)
admin.site.register(Account)
admin.site.register(Wallet)
admin.site.register(Transaction)
admin.site.register(Deposit)
admin.site.register(Withdrawal)
admin.site.register(RiskLimit)
