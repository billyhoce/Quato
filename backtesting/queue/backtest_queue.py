"""Redis-based distributed queue for backtest tasks."""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

import config
from backtesting.models.backtest_models import TaskRecord, TaskStatus

logger = logging.getLogger(__name__)


class BacktestQueue:
    """Redis-based queue for managing backtest tasks across multiple server instances."""

    # Redis key patterns
    QUEUE_KEY = "backtest:queue"
    TASK_KEY_PREFIX = "backtest:task:"
    SESSION_KEY_PREFIX = "session:"
    LOCK_KEY = "backtest:lock"
    GLOBAL_TASKS_KEY = "backtest:all_tasks"

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Establish connection to Redis."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Connected to Redis at %s", self.redis_url)

    async def close(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")

    # -------------------------------------------------------------------------
    # Task CRUD
    # -------------------------------------------------------------------------

    async def create_task(self, record: TaskRecord) -> None:
        """Persist a new TaskRecord to Redis.

        Args:
            record: Fully constructed TaskRecord (status should be QUEUED).
        """
        await self.connect()
        task_key = f"{self.TASK_KEY_PREFIX}{record.task_id}"
        await self.redis_client.hset(task_key, mapping=record.to_redis_hash())
        logger.info("Created task %s for session %s", record.task_id, record.session_id)

    async def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """Retrieve a task by ID.

        Returns:
            TaskRecord, or None if the task does not exist.
        """
        await self.connect()
        task_key = f"{self.TASK_KEY_PREFIX}{task_id}"
        data = await self.redis_client.hgetall(task_key)
        if not data:
            return None
        return TaskRecord.from_redis_hash(data)

    async def update_task(self, task_id: str, updates: Dict[str, Any]) -> None:
        """Apply a partial update to a task hash.

        Args:
            task_id: Task to update.
            updates: Fields to set (None → empty string, datetime → ISO string,
                     bool/float/TaskStatus/str → str()).
        """
        await self.connect()
        task_key = f"{self.TASK_KEY_PREFIX}{task_id}"

        string_updates: Dict[str, str] = {}
        for key, value in updates.items():
            if value is None:
                string_updates[key] = ""
            elif isinstance(value, bool):
                string_updates[key] = str(value)
            elif isinstance(value, datetime):
                string_updates[key] = value.isoformat()
            else:
                string_updates[key] = str(value)

        await self.redis_client.hset(task_key, mapping=string_updates)
        logger.info("Updated task %s: %s", task_id, list(updates.keys()))

    # -------------------------------------------------------------------------
    # Queue operations
    # -------------------------------------------------------------------------

    async def enqueue_task(self, task_id: str) -> None:
        """Push a task ID onto the left end of the FIFO queue."""
        await self.connect()
        await self.redis_client.lpush(self.QUEUE_KEY, task_id)
        logger.info("Enqueued task %s", task_id)

    async def dequeue_task(self, timeout: int = 5) -> Optional[str]:
        """Block until a task is available, then pop and return its ID.

        Args:
            timeout: Seconds to wait before returning None.
        """
        await self.connect()
        result = await self.redis_client.brpop(self.QUEUE_KEY, timeout=timeout)
        if result:
            _, task_id = result
            logger.info("Dequeued task %s", task_id)
            return task_id
        return None

    # -------------------------------------------------------------------------
    # Session index
    # -------------------------------------------------------------------------

    async def add_to_session(self, session_id: str, task_id: str) -> None:
        """Associate a task with a session and the global task set."""
        await self.connect()
        session_key = f"{self.SESSION_KEY_PREFIX}{session_id}:tasks"
        await self.redis_client.sadd(session_key, task_id)
        await self.redis_client.sadd(self.GLOBAL_TASKS_KEY, task_id)

    async def get_all_tasks(self) -> List[TaskRecord]:
        """Return all tasks across all sessions, sorted newest-first."""
        await self.connect()
        task_ids = await self.redis_client.smembers(self.GLOBAL_TASKS_KEY)

        if not task_ids:
            return []

        async with self.redis_client.pipeline() as pipe:
            for task_id in task_ids:
                pipe.hgetall(f"{self.TASK_KEY_PREFIX}{task_id}")
            results = await pipe.execute()

        tasks = [
            TaskRecord.from_redis_hash(data)
            for data in results
            if data
        ]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    async def get_session_tasks(self, session_id: str) -> List[TaskRecord]:
        """Return all tasks for a session, sorted newest-first.

        Uses a single pipeline round-trip to batch all HGETALL calls.
        """
        await self.connect()
        session_key = f"{self.SESSION_KEY_PREFIX}{session_id}:tasks"
        task_ids = await self.redis_client.smembers(session_key)

        if not task_ids:
            return []

        async with self.redis_client.pipeline() as pipe:
            for task_id in task_ids:
                pipe.hgetall(f"{self.TASK_KEY_PREFIX}{task_id}")
            results = await pipe.execute()

        tasks = [
            TaskRecord.from_redis_hash(data)
            for data in results
            if data  # skip if task hash was deleted
        ]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    # -------------------------------------------------------------------------
    # Distributed lock
    # -------------------------------------------------------------------------

    async def acquire_backtest_lock(self, task_id: str) -> bool:
        """Acquire the global backtest lock (SET NX EX).

        Returns:
            True if the lock was acquired, False if another task holds it.
        """
        await self.connect()
        acquired = await self.redis_client.set(
            self.LOCK_KEY,
            task_id,
            nx=True,
            ex=config.BACKTEST_LOCK_TTL_SECONDS,
        )
        if acquired:
            logger.info("Task %s acquired backtest lock", task_id)
        else:
            holder = await self.redis_client.get(self.LOCK_KEY)
            logger.warning("Task %s failed to acquire lock (held by %s)", task_id, holder)
        return bool(acquired)

    async def is_backtest_running(self) -> bool:
        """Return True if the lock is currently held."""
        await self.connect()
        return bool(await self.redis_client.exists(self.LOCK_KEY))

    # Atomic check-and-delete prevents TOCTOU: between a GET and a DELETE the
    # TTL could expire and another task could acquire the lock.
    _RELEASE_LOCK_SCRIPT = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
    """

    async def release_backtest_lock(self, task_id: str) -> None:
        """Release the lock only if this task currently holds it."""
        await self.connect()
        released = await self.redis_client.eval(
            self._RELEASE_LOCK_SCRIPT, 1, self.LOCK_KEY, task_id
        )
        if released:
            logger.info("Task %s released backtest lock", task_id)
        else:
            holder = await self.redis_client.get(self.LOCK_KEY)
            logger.warning(
                "Task %s tried to release lock held by %s", task_id, holder
            )

    # -------------------------------------------------------------------------
    # Failure recovery
    # -------------------------------------------------------------------------

    async def mark_running_as_failed(self) -> int:
        """Mark orphaned running tasks as failed on startup.

        Only acts when NO lock is held — a held lock means another healthy
        instance is actively running a backtest and must not be disrupted.

        Returns:
            Number of tasks marked as failed.
        """
        await self.connect()

        lock_holder = await self.redis_client.get(self.LOCK_KEY)
        if lock_holder:
            logger.info(
                "Skipping startup recovery: lock held by task %s "
                "(another instance is running a backtest).",
                lock_holder,
            )
            return 0

        logger.info("No active lock. Scanning for orphaned running tasks...")
        count = 0
        cursor = 0
        pattern = f"{self.TASK_KEY_PREFIX}*"

        while True:
            cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
            for key in keys:
                data = await self.redis_client.hgetall(key)
                if data.get("status") == TaskStatus.RUNNING:
                    await self.redis_client.hset(
                        key,
                        mapping={
                            "status": TaskStatus.FAILED,
                            "error_message": (
                                "Server crashed or restarted while task was running (orphaned)"
                            ),
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    count += 1
                    task_id = data.get("task_id", key.split(":")[-1])
                    logger.info("Marked orphaned task %s as failed", task_id)
            if cursor == 0:
                break

        if count:
            logger.info("Startup recovery: marked %d orphaned task(s) as failed", count)
        else:
            logger.info("No orphaned running tasks found")
        return count

    async def cleanup_stale_running_tasks(self) -> int:
        """Periodic cleanup: mark running tasks stale beyond the lock TTL as failed.

        Handles crashes where the lock expired but the task hash was not updated.
        Timestamps written by older code (naive UTC) are treated as UTC.

        Returns:
            Number of tasks marked as failed.
        """
        await self.connect()

        lock_holder = await self.redis_client.get(self.LOCK_KEY)
        stale_threshold = datetime.now(timezone.utc) - timedelta(
            seconds=config.BACKTEST_LOCK_TTL_SECONDS
        )

        count = 0
        cursor = 0
        pattern = f"{self.TASK_KEY_PREFIX}*"

        while True:
            cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
            for key in keys:
                data = await self.redis_client.hgetall(key)
                if data.get("status") != TaskStatus.RUNNING:
                    continue

                task_id = data.get("task_id", key.split(":")[-1])

                # The currently locked task is being actively processed — skip.
                if lock_holder and task_id == lock_holder:
                    continue

                started_at_str = data.get("started_at", "")
                if not started_at_str:
                    await self.redis_client.hset(
                        key,
                        mapping={
                            "status": TaskStatus.FAILED,
                            "error_message": "Task running without started_at (data corruption)",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    count += 1
                    logger.warning("Marked corrupted task %s as failed", task_id)
                    continue

                try:
                    started_at = datetime.fromisoformat(started_at_str)
                    # Normalise legacy naive timestamps (written with utcnow()) to UTC
                    if started_at.tzinfo is None:
                        started_at = started_at.replace(tzinfo=timezone.utc)

                    if started_at < stale_threshold:
                        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                        await self.redis_client.hset(
                            key,
                            mapping={
                                "status": TaskStatus.FAILED,
                                "error_message": (
                                    f"Task exceeded maximum runtime of "
                                    f"{config.BACKTEST_LOCK_TTL_SECONDS}s "
                                    f"(ran for {elapsed:.0f}s). Server likely crashed."
                                ),
                                "completed_at": datetime.now(timezone.utc).isoformat(),
                            },
                        )
                        count += 1
                        logger.info(
                            "Marked stale task %s as failed (running %.0fs)",
                            task_id,
                            elapsed,
                        )
                except (ValueError, TypeError) as exc:
                    logger.error(
                        "Could not parse started_at for task %s: %s", task_id, exc
                    )
            if cursor == 0:
                break

        if count:
            logger.info("Periodic cleanup: marked %d stale task(s) as failed", count)
        return count
