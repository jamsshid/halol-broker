from django.urls import path
from .dashboards import AdminFinancialStatsView
from .revenue import RevenueReportView
from .risk_view import (
    RiskAlertView,
    UpdateGlobalLimitsView,
    UpdateForbiddenInstrumentsView,
    GlobalRiskLimitAPI,
)
from .sharia_audit import ShariaAuditView, ShariaAuditExportView

urlpatterns = [
    path('financial-stats/', AdminFinancialStatsView.as_view(), name='admin-financial-stats'),
    path('revenue/', RevenueReportView.as_view(), name='admin-revenue'),
    path('risk/alerts/', RiskAlertView.as_view(), name='admin-risk-alerts'),
    path('risk/update-limits/', UpdateGlobalLimitsView.as_view(), name='admin-update-global-limits'),
    path('risk/update-forbidden-instruments/', UpdateForbiddenInstrumentsView.as_view(), name='admin-update-forbidden-instruments'),
    path('risk/global-limits/', GlobalRiskLimitAPI.as_view(), name='admin-global-risk-limits-api'),
    path('sharia/audit/', ShariaAuditView.as_view(), name='admin-sharia-audit'),
    path('sharia/audit/export/', ShariaAuditExportView.as_view(), name='admin-sharia-audit-export'),
]

