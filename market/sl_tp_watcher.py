"""
SL/TP Watcher - Real-time Stop Loss / Take Profit Monitoring
Uses Redis for price data and Celery for background processing.
"""
import logging
from decimal import Decimal
from typing import List, Dict, Any, Optional

from django.conf import settings
from django.utils import timezone

from market.redis_cache import price_cache
from trading.models import Position
from trading.services.trade_close import close_trade

logger = logging.getLogger(__name__)


class SLTPWatcher:
    """
    Real-time SL/TP monitoring service.
    Runs as Celery task to check positions against current market prices.
    """

    def __init__(self):
        self.price_cache = price_cache

    def check_positions(self) -> Dict[str, List[int]]:
        """
        Check all open positions for SL/TP hits.

        Returns:
            dict: Results with 'sl_hits' and 'tp_hits' position IDs
        """
        results = {
            'sl_hits': [],
            'tp_hits': [],
            'errors': []
        }

        try:
            # Get all open positions
            open_positions = Position.objects.filter(status=Position.Status.OPEN).select_related('instrument')

            for position in open_positions:
                try:
                    hit_type = self._check_single_position(position)
                    if hit_type == 'sl':
                        results['sl_hits'].append(position.id)
                    elif hit_type == 'tp':
                        results['tp_hits'].append(position.id)

                except Exception as e:
                    logger.error(f"Error checking position {position.id}: {e}")
                    results['errors'].append(position.id)

        except Exception as e:
            logger.error(f"Error in SL/TP watcher: {e}")

        return results

    def _check_single_position(self, position: Position) -> Optional[str]:
        """
        Check a single position for SL/TP hits.

        Args:
            position: Position instance

        Returns:
            str: 'sl' if stop loss hit, 'tp' if take profit hit, None otherwise
        """
        symbol = position.instrument.symbol
        current_price = self.price_cache.get_price_value(symbol)

        if not current_price:
            logger.debug(f"No price available for {symbol}, skipping position {position.id}")
            return None

        # Check based on position side
        if position.side == Position.Side.BUY:
            # For BUY positions: SL when price <= stop_loss, TP when price >= take_profit
            if current_price <= position.stop_loss:
                return 'sl'
            elif position.take_profit and current_price >= position.take_profit:
                return 'tp'

        elif position.side == Position.Side.SELL:
            # For SELL positions: SL when price >= stop_loss, TP when price <= take_profit
            if current_price >= position.stop_loss:
                return 'sl'
            elif position.take_profit and current_price <= position.take_profit:
                return 'tp'

        return None

    def execute_hits(self, sl_positions: List[int], tp_positions: List[int]) -> Dict[str, Any]:
        """
        Execute trade closures for hit positions.

        Args:
            sl_positions: List of position IDs that hit stop loss
            tp_positions: List of position IDs that hit take profit

        Returns:
            dict: Execution results
        """
        results = {
            'sl_closed': [],
            'tp_closed': [],
            'errors': []
        }

        # Close SL positions
        for position_id in sl_positions:
            try:
                position = Position.objects.get(id=position_id, status=Position.Status.OPEN)
                symbol = position.instrument.symbol
                current_price = self.price_cache.get_price_value(symbol)

                if current_price:
                    close_trade(
                        position_id=position_id,
                        closing_price=current_price,
                        reason="STOP_LOSS"
                    )
                    results['sl_closed'].append(position_id)
                    logger.info(f"Closed position {position_id} at SL: {current_price}")

            except Exception as e:
                logger.error(f"Failed to close SL position {position_id}: {e}")
                results['errors'].append({'position_id': position_id, 'error': str(e)})

        # Close TP positions
        for position_id in tp_positions:
            try:
                position = Position.objects.get(id=position_id, status=Position.Status.OPEN)
                symbol = position.instrument.symbol
                current_price = self.price_cache.get_price_value(symbol)

                if current_price:
                    close_trade(
                        position_id=position_id,
                        closing_price=current_price,
                        reason="TAKE_PROFIT"
                    )
                    results['tp_closed'].append(position_id)
                    logger.info(f"Closed position {position_id} at TP: {current_price}")

            except Exception as e:
                logger.error(f"Failed to close TP position {position_id}: {e}")
                results['errors'].append({'position_id': position_id, 'error': str(e)})

        return results


# Global instance
sl_tp_watcher = SLTPWatcher()


# Celery task
from celery import shared_task


@shared_task(bind=True, max_retries=3)
def check_sl_tp_positions(self):
    """
    Celery task to check all positions for SL/TP hits.
    Runs periodically (e.g., every 5-10 seconds).
    """
    try:
        logger.info("Starting SL/TP position check")

        # Check positions
        results = sl_tp_watcher.check_positions()

        # Execute hits if any
        if results['sl_hits'] or results['tp_hits']:
            execution_results = sl_tp_watcher.execute_hits(
                results['sl_hits'],
                results['tp_hits']
            )

            logger.info(f"SL/TP check completed: {execution_results}")
            return execution_results
        else:
            logger.debug("No SL/TP hits found")
            return {'message': 'No hits found'}

    except Exception as e:
        logger.error(f"SL/TP check task failed: {e}")
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries), exc=e)


@shared_task
def update_position_prices():
    """
    Periodic task to update position unrealized PnL.
    Can be run less frequently than SL/TP checks.
    """
    try:
        logger.info("Starting position price updates")

        open_positions = Position.objects.filter(status=Position.Status.OPEN).select_related('instrument')

        updated_count = 0
        for position in open_positions:
            try:
                symbol = position.instrument.symbol
                current_price = price_cache.get_price_value(symbol)

                if current_price:
                    # Calculate unrealized PnL
                    if position.side == Position.Side.BUY:
                        unrealized_pnl = (current_price - position.entry_price) * position.position_size
                    else:  # SELL
                        unrealized_pnl = (position.entry_price - current_price) * position.position_size

                    # Update position
                    position.unrealized_pnl = unrealized_pnl
                    position.save(update_fields=['unrealized_pnl'])

                    updated_count += 1

            except Exception as e:
                logger.error(f"Failed to update position {position.id}: {e}")

        logger.info(f"Updated {updated_count} positions")
        return {'updated': updated_count}

    except Exception as e:
        logger.error(f"Position price update task failed: {e}")
        raise