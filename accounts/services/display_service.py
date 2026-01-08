from decimal import Decimal
import logging
from typing import Dict, Any

from accounts.models import User, Account
from common.enums import AccountType, ComplianceMode

logger = logging.getLogger(__name__)

class PnLDisplayService:

    @staticmethod
    def _calculate_percent(pnl: Decimal, base_amount: Decimal) -> Decimal:
        if base_amount is None or base_amount == 0:
            return Decimal("0.00")

        percent = (pnl / base_amount) * Decimal("100")
        return percent.quantize(Decimal("0.01"))

    @staticmethod
    def format_pnl(
        *,
        user: User,
        account: Account,
        pnl: Decimal,
        base_amount: Decimal | None = None,
    ) -> Dict[str, Any]:
        if base_amount is None:
            base_amount = account.balance or Decimal("0.00")

        status: str
        if pnl > 0:
            status = "PROFIT"
        elif pnl < 0:
            status = "LOSS"
        else:
            status = "FLAT"

        pnl_percent = PnLDisplayService._calculate_percent(pnl, base_amount)

        is_ultra_calm = user.compliance_mode == ComplianceMode.ULTRA_CALM.value
        is_real_account = account.account_type == AccountType.REAL.value

        payload: Dict[str, Any]
        if is_ultra_calm and is_real_account:
            payload = {
                "is_blurred": True,
                "status": status,
                "pnl_percent": pnl_percent,
            }
        else:
            payload = {
                "is_blurred": False,
                "status": status,
                "pnl_amount": pnl.quantize(Decimal("0.01")),
                "pnl_percent": pnl_percent,
            }

        logger.info(
            "PnL display formatted",
            extra={
                "user_id": getattr(user, "id", None),
                "account_id": getattr(account, "id", None),
                "status": status,
                "is_blurred": payload["is_blurred"],
                "pnl_percent": str(pnl_percent),
            },
        )

        return payload

