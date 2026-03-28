"""Strategy Manager for handling strategy state per session - Redis-backed."""
import hashlib
import logging
import os
from typing import Optional

import redis.asyncio as redis
from google import genai

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
    SUMMARY_KEY_PREFIX = "strategy:summary:"
    SUMMARY_HASH_KEY_PREFIX = "strategy:summary_hash:"
    TITLE_KEY_PREFIX = "strategy:title:"
    TITLE_HASH_KEY_PREFIX = "strategy:title_hash:"

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

    async def get_or_create_summary(self, session_id: str, code: str) -> str:
        """Return a cached summary if the code hasn't changed, otherwise generate one."""
        await self.connect()
        code_hash = hashlib.sha256(code.encode()).hexdigest()

        cached_hash = await self._redis.get(
            f"{self.SUMMARY_HASH_KEY_PREFIX}{session_id}"
        )
        if cached_hash == code_hash:
            cached_summary = await self._redis.get(
                f"{self.SUMMARY_KEY_PREFIX}{session_id}"
            )
            if cached_summary:
                return cached_summary

        summary = await self._generate_summary(code)

        await self._redis.set(
            f"{self.SUMMARY_KEY_PREFIX}{session_id}", summary
        )
        await self._redis.set(
            f"{self.SUMMARY_HASH_KEY_PREFIX}{session_id}", code_hash
        )
        return summary

    async def get_or_create_title(self, session_id: str, code: str) -> str:
        """Return a cached short title if the code hasn't changed, otherwise generate one."""
        await self.connect()
        code_hash = hashlib.sha256(code.encode()).hexdigest()

        cached_hash = await self._redis.get(
            f"{self.TITLE_HASH_KEY_PREFIX}{session_id}"
        )
        if cached_hash == code_hash:
            cached_title = await self._redis.get(
                f"{self.TITLE_KEY_PREFIX}{session_id}"
            )
            if cached_title:
                return cached_title

        title = await self._generate_title(code)

        await self._redis.set(f"{self.TITLE_KEY_PREFIX}{session_id}", title)
        await self._redis.set(
            f"{self.TITLE_HASH_KEY_PREFIX}{session_id}", code_hash
        )
        return title

    @staticmethod
    async def _generate_title(code: str) -> str:
        """Call Gemini to produce a 3-6 word session title for the strategy."""
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "Give this trading strategy a concise title of 3-6 words that "
                "describes what it does. Output ONLY the title with no punctuation "
                "at the end and no extra explanation.\n\n"
                f"```python\n{code}\n```"
            ),
        )
        return response.text.strip()

    @staticmethod
    async def _generate_summary(code: str) -> str:
        """Call Gemini to produce a plain-English strategy summary."""
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "Summarize this trading strategy in 2-4 sentences of plain English. "
                "Focus on what the strategy does, what signals it uses, and its basic "
                "logic. Do not mention any libraries, frameworks, or implementation "
                "details — only describe the strategy itself. Do not include code.\n\n"
                f"```python\n{code}\n```"
            ),
        )
        return response.text