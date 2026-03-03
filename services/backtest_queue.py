"""Redis-based distributed queue for backtest tasks."""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import redis.asyncio as redis

import config

logger = logging.getLogger(__name__)


class BacktestQueue:
    """Redis-based queue for managing backtest tasks across multiple server instances."""
    
    # Redis key patterns
    QUEUE_KEY = "backtest:queue"
    TASK_KEY_PREFIX = "backtest:task:"
    SESSION_KEY_PREFIX = "session:"
    LOCK_KEY = "backtest:lock"
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize Redis connection.
        
        Args:
            redis_url: Redis connection URL (default: from REDIS_URL env var)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client: Optional[redis.Redis] = None
        
    async def connect(self):
        """Establish connection to Redis."""
        if self.redis_client is None:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info(f"Connected to Redis at {self.redis_url}")
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
    
    async def create_task(
        self,
        task_id: str,
        session_id: str,
        strategy_code: str,
        config_dict: Dict[str, Any]
    ) -> None:
        """Create a new backtest task in Redis.
        
        Args:
            task_id: Unique task identifier
            session_id: User session ID
            strategy_code: Trading strategy code
            config_dict: Backtest configuration as dict
        """
        await self.connect()
        
        task_data = {
            "task_id": task_id,
            "session_id": session_id,
            "status": "queued",
            "strategy_code": strategy_code,
            "config_json": json.dumps(config_dict),
            "created_at": datetime.utcnow().isoformat(),
            "started_at": "",
            "completed_at": "",
            "strategy_path": "",
            "results_file": "",
            "tearsheet_file": "",
            "error_message": ""
        }
        
        task_key = f"{self.TASK_KEY_PREFIX}{task_id}"
        await self.redis_client.hset(task_key, mapping=task_data)
        logger.info(f"Created task {task_id} for session {session_id}")
    
    async def enqueue_task(self, task_id: str) -> None:
        """Add task to the processing queue.
        
        Args:
            task_id: Task to enqueue
        """
        await self.connect()
        await self.redis_client.lpush(self.QUEUE_KEY, task_id)
        logger.info(f"Enqueued task {task_id}")
    
    async def dequeue_task(self, timeout: int = 5) -> Optional[str]:
        """Remove and return a task from the queue (blocking).
        
        Args:
            timeout: How long to wait for a task (seconds)
            
        Returns:
            Task ID or None if timeout
        """
        await self.connect()
        result = await self.redis_client.brpop(self.QUEUE_KEY, timeout=timeout)
        if result:
            _, task_id = result
            logger.info(f"Dequeued task {task_id}")
            return task_id
        return None
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task details.
        
        Args:
            task_id: Task to retrieve
            
        Returns:
            Task data dict or None if not found
        """
        await self.connect()
        task_key = f"{self.TASK_KEY_PREFIX}{task_id}"
        task_data = await self.redis_client.hgetall(task_key)
        
        if not task_data:
            return None
        
        # Convert success string to boolean for backward compatibility
        if "success" in task_data:
            task_data["success"] = task_data["success"].lower() == "true"
        
        return task_data
    
    async def update_task(
        self,
        task_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """Update task fields.
        
        Args:
            task_id: Task to update
            updates: Fields to update (status, error_message, etc.)
        """
        await self.connect()
        task_key = f"{self.TASK_KEY_PREFIX}{task_id}"
        
        # Convert non-string values to strings for Redis hash
        string_updates = {}
        for key, value in updates.items():
            if value is None:
                string_updates[key] = ""
            elif isinstance(value, bool):
                string_updates[key] = str(value)
            else:
                string_updates[key] = str(value)
        
        await self.redis_client.hset(task_key, mapping=string_updates)
        logger.info(f"Updated task {task_id}: {list(updates.keys())}")
    
    async def add_to_session(self, session_id: str, task_id: str) -> None:
        """Add task to session's task list.
        
        Args:
            session_id: User session
            task_id: Task to associate
        """
        await self.connect()
        session_key = f"{self.SESSION_KEY_PREFIX}{session_id}:tasks"
        await self.redis_client.sadd(session_key, task_id)
        logger.info(f"Added task {task_id} to session {session_id}")
    
    async def get_session_tasks(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a session.
        
        Args:
            session_id: User session
            
        Returns:
            List of task data dicts
        """
        await self.connect()
        session_key = f"{self.SESSION_KEY_PREFIX}{session_id}:tasks"
        task_ids = await self.redis_client.smembers(session_key)
        
        tasks = []
        for task_id in task_ids:
            task_data = await self.get_task(task_id)
            if task_data:
                tasks.append(task_data)
        
        # Sort by created_at descending (most recent first)
        tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return tasks
    
    async def acquire_backtest_lock(self, task_id: str) -> bool:
        """Acquire distributed lock for running backtest.
        
        Only one server instance can hold this lock at a time.
        
        Args:
            task_id: Task attempting to acquire lock
            
        Returns:
            True if lock acquired, False otherwise
        """
        await self.connect()
        # SET NX EX pattern: set if not exists, with expiration
        acquired = await self.redis_client.set(
            self.LOCK_KEY,
            task_id,
            nx=True,
            ex=config.BACKTEST_LOCK_TTL_SECONDS
        )
        
        if acquired:
            logger.info(f"Task {task_id} acquired backtest lock")
        else:
            current_holder = await self.redis_client.get(self.LOCK_KEY)
            logger.warning(f"Task {task_id} failed to acquire lock (held by {current_holder})")
        
        return bool(acquired)
    
    async def is_backtest_running(self) -> bool:
        """Check if any backtest is currently running.
        
        Returns:
            True if a lock is held (backtest running), False otherwise
        """
        await self.connect()
        lock_exists = await self.redis_client.exists(self.LOCK_KEY)
        return bool(lock_exists)
    
    async def release_backtest_lock(self, task_id: str) -> None:
        """Release distributed lock.
        
        Args:
            task_id: Task releasing the lock (must be current holder)
        """
        await self.connect()
        current_holder = await self.redis_client.get(self.LOCK_KEY)
        
        if current_holder == task_id:
            await self.redis_client.delete(self.LOCK_KEY)
            logger.info(f"Task {task_id} released backtest lock")
        else:
            logger.warning(f"Task {task_id} tried to release lock held by {current_holder}")
    
    async def mark_running_as_failed(self) -> int:
        """Mark orphaned running tasks as failed (for startup recovery).
        
        Called when server restarts. Only marks tasks as failed if NO lock is held,
        meaning no server is actively running a backtest. This prevents killing
        legitimate backtests running on other healthy server instances.
        
        Returns:
            Number of tasks marked as failed
        """
        await self.connect()
        
        # Check if any server is currently running a backtest
        lock_holder = await self.redis_client.get(self.LOCK_KEY)
        
        if lock_holder:
            logger.info(
                f"Skipping startup recovery: backtest lock is held by task {lock_holder}. "
                "Another server instance is actively running a backtest."
            )
            return 0
        
        # No lock held - safe to clean up orphaned tasks
        logger.info("No active backtest lock found. Checking for orphaned running tasks...")
        
        # Scan for all task keys
        count = 0
        cursor = 0
        pattern = f"{self.TASK_KEY_PREFIX}*"
        
        while True:
            cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                task_data = await self.redis_client.hgetall(key)
                if task_data.get("status") == "running":
                    await self.redis_client.hset(
                        key,
                        mapping={
                            "status": "failed",
                            "error_message": "Server crashed or restarted while task was running (orphaned task)",
                            "completed_at": datetime.utcnow().isoformat()
                        }
                    )
                    count += 1
                    task_id = task_data.get("task_id", key.split(":")[-1])
                    logger.info(f"Marked orphaned task {task_id} as failed")
            
            if cursor == 0:
                break
        
        if count > 0:
            logger.info(f"Startup recovery: marked {count} orphaned running tasks as failed")
        else:
            logger.info("No orphaned running tasks found")
        
        return count
    
    async def cleanup_stale_running_tasks(self) -> int:
        """Mark stale running tasks as failed (periodic cleanup).
        
        Detects tasks that have been "running" for longer than the lock TTL
        without an active lock. This handles the case where a server crashes
        mid-backtest but no server restarts to trigger startup recovery.
        
        Should be called periodically (e.g., every 15 minutes) by a background task.
        
        Returns:
            Number of tasks marked as failed
        """
        await self.connect()
        
        # Check if any server is currently running a backtest
        lock_holder = await self.redis_client.get(self.LOCK_KEY)
        
        if lock_holder:
            # A lock is held - there's an active backtest
            # Check if the locked task is actually stale
            locked_task = await self.get_task(lock_holder)
            
            if locked_task and locked_task.get("status") == "running":
                started_at_str = locked_task.get("started_at")
                if started_at_str:
                    started_at = datetime.fromisoformat(started_at_str)
                    running_duration = (datetime.utcnow() - started_at).total_seconds()
                    
                    # If task has been running longer than lock TTL + grace period,
                    # the lock must have been renewed or is about to expire
                    if running_duration > config.BACKTEST_LOCK_TTL_SECONDS * 1.1:
                        logger.warning(
                            f"Task {lock_holder} has been running for {running_duration:.0f}s "
                            f"(>{config.BACKTEST_LOCK_TTL_SECONDS}s). Lock may be expired."
                        )
        
        # Find all running tasks
        count = 0
        cursor = 0
        pattern = f"{self.TASK_KEY_PREFIX}*"
        stale_threshold = datetime.utcnow() - timedelta(seconds=config.BACKTEST_LOCK_TTL_SECONDS)
        
        while True:
            cursor, keys = await self.redis_client.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                task_data = await self.redis_client.hgetall(key)
                
                if task_data.get("status") == "running":
                    task_id = task_data.get("task_id", key.split(":")[-1])
                    
                    # Skip if this is the currently locked task
                    if lock_holder and task_id == lock_holder:
                        continue
                    
                    # Check if task is stale
                    started_at_str = task_data.get("started_at")
                    if not started_at_str:
                        # No started_at timestamp - mark as failed immediately
                        logger.warning(f"Task {task_id} is running but has no started_at timestamp")
                        await self.redis_client.hset(
                            key,
                            mapping={
                                "status": "failed",
                                "error_message": "Task running without started_at timestamp (data corruption)",
                                "completed_at": datetime.utcnow().isoformat()
                            }
                        )
                        count += 1
                        logger.info(f"Marked corrupted task {task_id} as failed")
                        continue
                    
                    try:
                        started_at = datetime.fromisoformat(started_at_str)
                        
                        # Is task older than lock TTL?
                        if started_at < stale_threshold:
                            running_duration = (datetime.utcnow() - started_at).total_seconds()
                            await self.redis_client.hset(
                                key,
                                mapping={
                                    "status": "failed",
                                    "error_message": (
                                        f"Task exceeded maximum runtime of {config.BACKTEST_LOCK_TTL_SECONDS}s "
                                        f"(ran for {running_duration:.0f}s). Server likely crashed."
                                    ),
                                    "completed_at": datetime.utcnow().isoformat()
                                }
                            )
                            count += 1
                            logger.info(
                                f"Marked stale task {task_id} as failed "
                                f"(running for {running_duration:.0f}s)"
                            )
                    except (ValueError, TypeError) as e:
                        logger.error(f"Failed to parse started_at for task {task_id}: {e}")
            
            if cursor == 0:
                break
        
        if count > 0:
            logger.info(f"Periodic cleanup: marked {count} stale running tasks as failed")
        
        return count
