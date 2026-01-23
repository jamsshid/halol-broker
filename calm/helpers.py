"""
Calm mode helpers - PnL adjustment hooks with Redis caching
Backend signals only (no UI), mode-based stress-free flag.
Uses Redis for temporary state storage.
"""
import json
import logging
from decimal import Decimal
from typing import Dict, Any, Optional

from django.dispatch import Signal
from django.conf import settings

from calm.ultra import UltraCalmMode
from calm.semi import SemiCalmMode
from trading.models import Position

logger = logging.getLogger(__name__)

# Signal for PnL display adjustment (backend only)
pnl_display_adjustment = Signal()  # providing_args=['position', 'mode', 'stress_free_flag']


class CalmStateCache:
    """
    Redis-based cache for calm mode state.
    Stores stress flags and blurred PnL data temporarily.
    """

    CALM_KEY_PREFIX = "calm"
    STRESS_FLAG_TTL = 3600  # 1 hour
    PNL_STATE_TTL = 1800    # 30 minutes

    def __init__(self):
        self.redis_client = self._get_redis_client()

    def _get_redis_client(self):
        """Get Redis client with fallback"""
        try:
            from django_redis import get_redis_connection
            return get_redis_connection("default")
        except Exception as e:
            logger.warning(f"Redis connection failed for calm state: {e}")
            return None

    def _make_calm_key(self, position_id: int) -> str:
        """Create Redis key for calm state"""
        return f"{self.CALM_KEY_PREFIX}:{position_id}"

    def set_stress_flag(self, position_id: int, stress_free: bool, mode: str) -> bool:
        """
        Set stress-free flag for position.

        Args:
            position_id: Position ID
            stress_free: Whether stress-free mode is active
            mode: Calm mode ('ULTRA' or 'SEMI')

        Returns:
            bool: Success status
        """
        try:
            if not self.redis_client:
                return False

            key = self._make_calm_key(position_id)
            data = {
                'stress_free': stress_free,
                'mode': mode,
                'timestamp': None  # Will be set by Redis
            }

            self.redis_client.hset(key, 'stress_flag', json.dumps(data))
            self.redis_client.expire(key, self.STRESS_FLAG_TTL)

            logger.debug(f"Set stress flag for position {position_id}: {stress_free}")
            return True

        except Exception as e:
            logger.error(f"Failed to set stress flag for position {position_id}: {e}")
            return False

    def get_stress_flag(self, position_id: int) -> Optional[Dict[str, Any]]:
        """
        Get stress-free flag for position.

        Args:
            position_id: Position ID

        Returns:
            dict: Stress flag data or None
        """
        try:
            if not self.redis_client:
                return None

            key = self._make_calm_key(position_id)
            data = self.redis_client.hget(key, 'stress_flag')

            if data:
                return json.loads(data)
            return None

        except Exception as e:
            logger.error(f"Failed to get stress flag for position {position_id}: {e}")
            return None

    def set_blurred_pnl(self, position_id: int, blurred_pnl: Decimal, actual_pnl: Decimal) -> bool:
        """
        Set blurred PnL state for position.

        Args:
            position_id: Position ID
            blurred_pnl: Display PnL (adjusted)
            actual_pnl: Actual PnL (hidden)

        Returns:
            bool: Success status
        """
        try:
            if not self.redis_client:
                return False

            key = self._make_calm_key(position_id)
            data = {
                'blurred_pnl': str(blurred_pnl),
                'actual_pnl': str(actual_pnl),
                'timestamp': None
            }

            self.redis_client.hset(key, 'pnl_state', json.dumps(data))
            self.redis_client.expire(key, self.PNL_STATE_TTL)

            logger.debug(f"Set blurred PnL for position {position_id}: {blurred_pnl}")
            return True

        except Exception as e:
            logger.error(f"Failed to set blurred PnL for position {position_id}: {e}")
            return False

    def get_blurred_pnl(self, position_id: int) -> Optional[Dict[str, Any]]:
        """
        Get blurred PnL state for position.

        Args:
            position_id: Position ID

        Returns:
            dict: PnL state data or None
        """
        try:
            if not self.redis_client:
                return None

            key = self._make_calm_key(position_id)
            data = self.redis_client.hget(key, 'pnl_state')

            if data:
                pnl_data = json.loads(data)
                # Convert back to Decimal
                pnl_data['blurred_pnl'] = Decimal(pnl_data['blurred_pnl'])
                pnl_data['actual_pnl'] = Decimal(pnl_data['actual_pnl'])
                return pnl_data
            return None

        except Exception as e:
            logger.error(f"Failed to get blurred PnL for position {position_id}: {e}")
            return None

    def clear_position_state(self, position_id: int) -> bool:
        """
        Clear all calm state for a position (when trade closes).

        Args:
            position_id: Position ID

        Returns:
            bool: Success status
        """
        try:
            if not self.redis_client:
                return False

            key = self._make_calm_key(position_id)
            return bool(self.redis_client.delete(key))

        except Exception as e:
            logger.error(f"Failed to clear calm state for position {position_id}: {e}")
            return False

    def get_all_calm_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all calm states (for debugging/admin).

        Returns:
            dict: All calm state data
        """
        try:
            if not self.redis_client:
                return {}

            states = {}
            keys = self.redis_client.keys(f"{self.CALM_KEY_PREFIX}:*")

            for key in keys:
                try:
                    position_id = key.decode().split(':', 1)[1] if isinstance(key, bytes) else key.split(':', 1)[1]
                    stress_flag = self.redis_client.hget(key, 'stress_flag')
                    pnl_state = self.redis_client.hget(key, 'pnl_state')

                    state_data = {}
                    if stress_flag:
                        state_data['stress_flag'] = json.loads(stress_flag)
                    if pnl_state:
                        state_data['pnl_state'] = json.loads(pnl_state)

                    if state_data:
                        states[position_id] = state_data

                except Exception as e:
                    logger.error(f"Error parsing calm state for key {key}: {e}")

            return states

        except Exception as e:
            logger.error(f"Failed to get all calm states: {e}")
            return {}


# Global instance
calm_state_cache = CalmStateCache()


def get_mode_policy(mode: str):
    """
    Get mode policy class.

    Args:
        mode: 'ULTRA' or 'SEMI'

    Returns:
        Mode policy class
    """
    if mode == Position.Mode.ULTRA:
        return UltraCalmMode
    elif mode == Position.Mode.SEMI:
        return SemiCalmMode
    else:
        raise ValueError(f"Unknown mode: {mode}")


def get_stress_free_flag(mode: str) -> bool:
    """
    Get stress-free flag based on mode.

    Args:
        mode: 'ULTRA' or 'SEMI'

    Returns:
        True if stress-free mode enabled
    """
    policy = get_mode_policy(mode)
    return policy.is_stress_free()


def send_pnl_adjustment_signal(position: Position, pnl: Decimal):
    """
    Send PnL adjustment signal for mode-based display.
    Backend only - UI will listen to this signal.

    Args:
        position: Position instance
        pnl: PnL amount
    """
    stress_free = get_stress_free_flag(position.mode)

    # Cache stress flag in Redis
    calm_state_cache.set_stress_flag(position.id, stress_free, position.mode)

    pnl_display_adjustment.send(
        sender=Position,
        position=position,
        mode=position.mode,
        stress_free_flag=stress_free,
        pnl=pnl
    )


def get_adjusted_pnl_display(position: Position, actual_pnl: Decimal) -> Decimal:
    """
    Get adjusted PnL for display based on calm mode.
    Uses Redis cache for state persistence.

    Args:
        position: Position instance
        actual_pnl: Actual PnL from calculation

    Returns:
        Decimal: Display PnL (may be blurred/adjusted)
    """
    try:
        # Check if we have cached blurred PnL
        cached_pnl = calm_state_cache.get_blurred_pnl(position.id)
        if cached_pnl:
            return cached_pnl['blurred_pnl']

        # Calculate adjusted PnL based on mode
        policy = get_mode_policy(position.mode)
        adjusted_pnl = policy.adjust_pnl(actual_pnl)

        # Cache the blurred PnL
        calm_state_cache.set_blurred_pnl(position.id, adjusted_pnl, actual_pnl)

        return adjusted_pnl

    except Exception as e:
        logger.error(f"Failed to get adjusted PnL for position {position.id}: {e}")
        return actual_pnl


def clear_calm_state_on_close(position_id: int):
    """
    Clear calm state when position closes.
    Should be called from trade close service.

    Args:
        position_id: Position ID
    """
    calm_state_cache.clear_position_state(position_id)
    logger.info(f"Cleared calm state for closed position {position_id}")
