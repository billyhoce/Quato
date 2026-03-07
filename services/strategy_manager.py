"""Strategy Manager for handling strategy state per session - Redis-backed."""
import logging
import os
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manages per-session strategy code and conversation turn counts in Redis.

    All state is stored in Redis so every server instance shares the same view,
    enabling horizontal scaling without sticky sessions.

    Key schema:
        strategy:{session_id}       — current strategy code (string)
        session:turns:{session_id}  — conversation turn counter (integer)
    """

    STRATEGY_KEY_PREFIX = "strategy:"
    TURNS_KEY_PREFIX = "session:turns:"

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis: Optional[redis.Redis] = None

    async def connect(self) -> None:
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
            logger.info("StrategyManager connected to Redis")

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def get_strategy(self, session_id: str) -> Optional[str]:
        await self.connect()
        return await self._redis.get(f"{self.STRATEGY_KEY_PREFIX}{session_id}")

    async def set_strategy(self, session_id: str, code: str) -> None:
        await self.connect()
        await self._redis.set(f"{self.STRATEGY_KEY_PREFIX}{session_id}", code)
        logger.info(f"Strategy updated for session {session_id}")

    async def has_strategy(self, session_id: str) -> bool:
        await self.connect()
        return bool(await self._redis.exists(f"{self.STRATEGY_KEY_PREFIX}{session_id}"))

    async def get_and_increment_turn(self, session_id: str) -> int:
        """Atomically return the current turn count, then increment it.

        Returns 0 on the first call for a session (first turn), 1 on the second, etc.
        Uses Redis INCR so concurrent requests across instances are safe.
        """
        await self.connect()
        # INCR returns the value *after* incrementing, so subtract 1 for the
        # "before" value that represents which turn we're currently on.
        new_count = await self._redis.incr(f"{self.TURNS_KEY_PREFIX}{session_id}")
        return new_count - 1