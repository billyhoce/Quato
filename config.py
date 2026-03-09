"""Application configuration settings."""

# Distributed lock TTL (Time To Live) in seconds
# This prevents deadlocks if a server crashes while holding the lock
# Set to 3 hours to accommodate long-running backtests
BACKTEST_LOCK_TTL_SECONDS: int = 3 * 60 * 60  # 3 hours

# Worker configuration
WORKER_QUEUE_TIMEOUT_SECONDS: int = 5  # How long worker waits for new tasks
WORKER_SHUTDOWN_TIMEOUT_SECONDS: float = 30.0  # Grace period for shutdown
WORKER_CLEANUP_INTERVAL_SECONDS: int = 15 * 60  # Run cleanup every 15 minutes

# Agent retry configuration
MAX_AGENT_RETRIES: int = 5  # Maximum number of automatic retries with agent for code errors
