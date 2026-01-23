# Redis Integration Setup Guide

## Overview
Halol Broker uses Redis for high-performance caching of market data, real-time SL/TP monitoring, and temporary state storage. Redis is **never used as source of truth** - all critical data remains in PostgreSQL.

## Architecture

### 1. Global Redis Configuration
- **Location**: `core/settings.py`
- **Purpose**: Django cache backend and Celery broker
- **TTL**: Configurable per use case

### 2. Market Price Cache
- **File**: `market/redis_cache.py`
- **Purpose**: Fast price lookups for SL/TP monitoring
- **Key Format**: `price:{SYMBOL}`
- **TTL**: 10 seconds

### 3. Candlestick Aggregation
- **File**: `market/services/candles.py`
- **Purpose**: Real-time OHLC data for charts
- **Keys**:
  - `tick:{SYMBOL}` - Raw price ticks (TTL: 5 min)
  - `candle:{SYMBOL}:{TIMEFRAME}:{PERIOD}` - Aggregated candles (TTL: 1 hour)

### 4. SL/TP Watcher
- **File**: `market/sl_tp_watcher.py`
- **Purpose**: Real-time stop loss/take profit monitoring
- **Celery Task**: `check_sl_tp_positions` (runs every 5-10 seconds)

### 5. Calm Mode State
- **File**: `calm/helpers.py`
- **Purpose**: Temporary storage of stress-free flags and blurred PnL
- **Key Format**: `calm:{POSITION_ID}`
- **TTL**: 1 hour for flags, 30 min for PnL

## Installation & Setup

### 1. Install Redis Server
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:alpine
```

### 2. Environment Variables
Add to your `.env` file:
```env
REDIS_URL=redis://localhost:6379/0
```

### 3. Start Celery Worker
```bash
# Activate virtual environment
source venv/bin/activate

# Start worker
celery -A core worker -l info

# Or with beat scheduler for periodic tasks
celery -A core worker -l info -B
```

### 4. Periodic Tasks Setup
Add to your Django settings or create a management command:

```python
# In settings.py or separate config
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'check-sl-tp-positions': {
        'task': 'market.sl_tp_watcher.check_sl_tp_positions',
        'schedule': 5.0,  # Every 5 seconds
    },
    'update-position-prices': {
        'task': 'market.sl_tp_watcher.update_position_prices',
        'schedule': 30.0,  # Every 30 seconds
    },
}
```

## Redis Failure Handling

### Graceful Degradation
- **Price Cache**: Falls back to mock data generation
- **SL/TP Watcher**: Skips monitoring (logs warning)
- **Candlesticks**: Uses mock data generation
- **Calm Mode**: Skips Redis operations (no UI impact)

### Monitoring
```python
# Check Redis connectivity
from django.core.cache import cache
cache.set('test_key', 'test_value', 10)
assert cache.get('test_key') == 'test_value'
```

## Key Naming Convention

```
price:{SYMBOL}              # Market prices
tick:{SYMBOL}               # Raw price ticks
candle:{SYMBOL}:{TF}:{TS}   # Aggregated candles
calm:{POSITION_ID}          # Calm mode state
```

## Performance Considerations

### Memory Usage
- Price cache: ~1KB per symbol
- Tick storage: ~100KB per symbol (24h rolling)
- Candle cache: ~50KB per symbol/timeframe
- Calm state: ~1KB per active position

### Connection Pooling
- Django Redis handles connection pooling automatically
- Max connections: 20 (configurable)

### TTL Strategy
- Short TTL for volatile data (prices: 10s)
- Medium TTL for derived data (candles: 1h)
- Long TTL for session data (calm state: 1h)

## Testing

### Unit Tests
```bash
python manage.py test market.tests.test_redis_integration
```

### Redis Mocking
Tests automatically mock Redis when unavailable, ensuring system continues to function.

### Integration Tests
- Test with Redis enabled
- Test with Redis disabled
- Verify fallback behavior

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running
   - Verify REDIS_URL in environment
   - Check firewall/network connectivity

2. **Celery Tasks Not Running**
   - Ensure Celery worker is started
   - Check Celery logs for errors
   - Verify task imports

3. **Memory Issues**
   - Monitor Redis memory usage
   - Adjust TTL values if needed
   - Clear old keys periodically

### Monitoring Commands
```bash
# Redis info
redis-cli info

# Check connected clients
redis-cli client list

# Monitor commands (debugging)
redis-cli monitor
```

## Security Notes

- Redis should be password-protected in production
- Use separate Redis instances for different environments
- Monitor for unauthorized access
- Regular backup of critical Redis data (if any)

## Production Deployment

### Redis Cluster (Optional)
For high availability, consider Redis Cluster or Redis Sentinel.

### Persistence
Configure Redis persistence (RDB/AOF) based on your durability requirements.

### Backup
While Redis is not source of truth, backup important cached data if needed.