from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api.account_views import AccountViewSet, TransactionViewSet
from .api.deposit_views import DepositViewSet
from .api.withdrawal_views import WithdrawalViewSet
from .api.wallet_integration_views import (
    WalletLockView,
    WalletReleaseView,
    WalletApplyPnLView,
)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .api.account_views import AccountViewSet, TransactionViewSet
from .api.deposit_views import DepositViewSet
from .api.withdrawal_views import WithdrawalViewSet
from .api.wallet_integration_views import (
    WalletLockView,
    WalletReleaseView,
    WalletApplyPnLView,
)
from .api.auth_views import (
    register_view,
    login_view,
    google_auth_view,
    logout_view,
    user_profile_view,
    update_profile_view,
    change_password_view,
)

router = DefaultRouter()
router.register(r"accounts", AccountViewSet, basename="account")
router.register(r"transactions", TransactionViewSet, basename="transaction")
router.register(r"deposits", DepositViewSet, basename="deposit")
router.register(r"withdrawals", WithdrawalViewSet, basename="withdrawal")

urlpatterns = [
    # Router URLs
    path("", include(router.urls)),
    # Auth endpoints
    path("auth/register/", register_view, name="auth-register"),
    path("auth/login/", login_view, name="auth-login"),
    
    path("auth/google/", google_auth_view, name="auth-google"),
    path("auth/logout/", logout_view, name="auth-logout"),
    path("auth/profile/", user_profile_view, name="auth-profile"),
    path("auth/profile/update/", update_profile_view, name="auth-profile-update"),
    path("auth/change-password/", change_password_view, name="auth-change-password"),
    # JWT token refresh
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # Wallet integration endpoints for Backend 1
    path("wallet/lock/", WalletLockView.as_view(), name="wallet-lock"),
    path("wallet/release/", WalletReleaseView.as_view(), name="wallet-release"),
    path("wallet/apply-pnl/", WalletApplyPnLView.as_view(), name="wallet-apply-pnl"),
]
