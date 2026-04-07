"""Background worker for processing backtest tasks."""
import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import config
from models.backtest_models import BacktestConfig, BacktestResults, TaskStatus
from services.backtest_queue import BacktestQueue
from services.object_store import ObjectStoreService
from backtesting_orchestrator.orchestrator import BacktestingOrchestrator

logger = logging.getLogger(__name__)


class BacktestWorker:
    """Async worker that processes backtest tasks from the Redis queue."""

    def __init__(
        self,
        queue: BacktestQueue,
        base_dir: Path,
        object_store: ObjectStoreService,
    ) -> None:
        self.queue = queue
        self.base_dir = base_dir
        self.object_store = object_store
        self.orchestrator: Optional[BacktestingOrchestrator] = None
        self.running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background worker loops."""
        if self.running:
            logger.warning("Worker is already running")
            return
        self.running = True
        self._processing_task = asyncio.create_task(self._run_processing_loop())
        self._cleanup_task = asyncio.create_task(self._run_cleanup_loop())
        logger.info("Backtest worker started (processing + cleanup tasks)")

    async def stop(self, timeout: Optional[float] = None) -> None:
        """Stop the worker gracefully, waiting up to *timeout* seconds."""
        if not self.running:
            return
        if timeout is None:
            timeout = config.WORKER_SHUTDOWN_TIMEOUT_SECONDS

        logger.info("Stopping backtest worker...")
        self.running = False

        tasks = [t for t in (self._processing_task, self._cleanup_task) if t]
        if tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Worker tasks did not stop within %.0fs, cancelling", timeout
                )
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Backtest worker stopped")

    # -------------------------------------------------------------------------
    # Internal loops
    # -------------------------------------------------------------------------

    async def _run_processing_loop(self) -> None:
        logger.info("Processing loop started")
        while self.running:
            try:
                # Avoid dequeuing when a peer already holds the lock.
                if await self.queue.is_backtest_running():
                    await asyncio.sleep(config.WORKER_QUEUE_TIMEOUT_SECONDS)
                    continue

                task_id = await self.queue.dequeue_task(
                    timeout=config.WORKER_QUEUE_TIMEOUT_SECONDS
                )
                if task_id:
                    await self._process_task(task_id)

            except asyncio.CancelledError:
                logger.info("Processing loop cancelled")
                break
            except Exception as exc:
                logger.error("Error in processing loop: %s", exc, exc_info=True)
                await asyncio.sleep(1)

        logger.info("Processing loop exited")

    async def _run_cleanup_loop(self) -> None:
        logger.info("Cleanup loop started")
        while self.running:
            try:
                await asyncio.sleep(config.WORKER_CLEANUP_INTERVAL_SECONDS)
                if not self.running:
                    break
                logger.info("Running periodic stale task cleanup...")
                failed = await self.queue.cleanup_stale_running_tasks()
                if failed:
                    logger.warning("Cleanup marked %d stale task(s) as failed", failed)
                else:
                    logger.debug("Cleanup found no stale tasks")

            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as exc:
                logger.error("Error in cleanup loop: %s", exc, exc_info=True)
                await asyncio.sleep(60)

        logger.info("Cleanup loop exited")

    # -------------------------------------------------------------------------
    # Task processing
    # -------------------------------------------------------------------------

    async def _process_task(self, task_id: str) -> None:
        """Execute one backtest task end-to-end and record success or failure."""
        logger.info("Processing task %s", task_id)
        lock_acquired = False

        try:
            # Lazy-initialise the orchestrator on the first task to avoid
            # blocking the event loop at startup (prepare_free_data makes
            # synchronous HTTP calls to QuantRocket that can take minutes).
            if self.orchestrator is None:
                logger.info("Initialising BacktestingOrchestrator (first task)...")
                self.orchestrator = await asyncio.to_thread(BacktestingOrchestrator)
                logger.info("BacktestingOrchestrator initialised")

            task_data = await self.queue.get_task(task_id)
            if not task_data:
                logger.error("Task %s not found in Redis", task_id)
                return

            lock_acquired = await self.queue.acquire_backtest_lock(task_id)
            if not lock_acquired:
                # Re-queue and yield — another worker holds the lock.
                logger.info("Could not acquire lock for task %s, re-queuing", task_id)
                await self.queue.enqueue_task(task_id)
                await asyncio.sleep(2)
                return

            await self.queue.update_task(task_id, {
                "status": TaskStatus.RUNNING,
                "started_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info("Task %s status: running", task_id)

            # Deserialise config; Pydantic v2 coerces ISO date strings to date.
            task_config = BacktestConfig(**json.loads(task_data.config_json))

            try:
                results: BacktestResults
                csv_object_key: str
                tearsheet_object_key: Optional[str]
                results, csv_object_key, tearsheet_object_key = await asyncio.to_thread(
                    self.orchestrator.backtest_strategy_from_code,
                    strategy_code=task_data.strategy_code,
                    config=task_config,
                    base_dir=self.base_dir,
                    object_store=self.object_store,
                    task_id=task_id,
                )

                update_fields = {
                    "status": TaskStatus.COMPLETE,
                    "success": True,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "csv_object_key": csv_object_key,
                    "total_return": results.total_return,
                    "sharpe_ratio": results.sharpe_ratio,
                    "max_drawdown": results.max_drawdown,
                    "execution_time": results.execution_time,
                }
                if tearsheet_object_key:
                    update_fields["tearsheet_object_key"] = tearsheet_object_key
                await self.queue.update_task(task_id, update_fields)
                logger.info("Task %s complete", task_id)

            except Exception as backtest_error:
                error_msg = f"Backtest failed:\n{backtest_error}\n{traceback.format_exc()}"
                logger.error("Task %s failed: %s", task_id, error_msg)
                await self.queue.update_task(task_id, {
                    "status": TaskStatus.FAILED,
                    "success": False,
                    "error_message": error_msg,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })

        except Exception as exc:
            error_msg = f"Worker error: {exc}\n{traceback.format_exc()}"
            logger.error("Task %s failed: %s", task_id, error_msg)
            try:
                await self.queue.update_task(task_id, {
                    "status": TaskStatus.FAILED,
                    "success": False,
                    "error_message": error_msg,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as update_exc:
                logger.error(
                    "Failed to update failed status for task %s: %s", task_id, update_exc
                )

        finally:
            if lock_acquired:
                try:
                    await self.queue.release_backtest_lock(task_id)
                except Exception as exc:
                    logger.error(
                        "Failed to release lock for task %s: %s", task_id, exc
                    )
