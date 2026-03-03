"""Background worker for processing backtest tasks."""
import asyncio
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from services.backtest_queue import BacktestQueue
from backtesting_orchestrator.orchestrator import BacktestingOrchestrator
from models.backtest_models import BacktestConfig

logger = logging.getLogger(__name__)


class BacktestWorker:
    """Async worker that processes backtest tasks from Redis queue."""
    
    def __init__(self, queue: BacktestQueue, base_dir: Path):
        """Initialize worker.
        
        Args:
            queue: Redis queue service
            base_dir: Base directory for strategy and result files
        """
        self.queue = queue
        self.base_dir = base_dir
        self.orchestrator = BacktestingOrchestrator()
        self.running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the background worker."""
        if self.running:
            logger.warning("Worker is already running")
            return
        
        self.running = True
        self._processing_task = asyncio.create_task(self._run_processing_loop())
        self._cleanup_task = asyncio.create_task(self._run_cleanup_loop())
        logger.info("Backtest worker started (processing + cleanup tasks)")
    
    async def stop(self, timeout: Optional[float] = None) -> None:
        """Stop the background worker gracefully.
        
        Args:
            timeout: How long to wait for current task to complete (seconds).
                    Defaults to config value.
        """
        if not self.running:
            return
        
        if timeout is None:
            timeout = config.WORKER_SHUTDOWN_TIMEOUT_SECONDS
        
        logger.info("Stopping backtest worker...")
        self.running = False
        
        # Stop both tasks
        tasks = []
        if self._processing_task:
            tasks.append(self._processing_task)
        if self._cleanup_task:
            tasks.append(self._cleanup_task)
        
        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Worker tasks did not stop within {timeout}s, cancelling")
                for task in tasks:
                    if not task.done():
                        task.cancel()
                # Wait for cancellations to complete
                await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("Backtest worker stopped")
    
    async def _run_processing_loop(self) -> None:
        """Main worker loop - dequeue and process tasks."""
        logger.info("Processing loop started")
        
        while self.running:
            try:
                # Check if a backtest is already running before dequeuing
                # This prevents unnecessary dequeue/re-queue cycles when lock is held
                # Note: Small race window exists if multiple workers check simultaneously,
                # but lock acquisition ensures only one task executes. Any duplicates
                # are safely re-queued. This is acceptable and much better than always
                # dequeuing regardless of lock status.
                if await self.queue.is_backtest_running():
                    # Another worker is running a backtest, wait before checking again
                    await asyncio.sleep(config.WORKER_QUEUE_TIMEOUT_SECONDS)
                    continue
                
                # No lock held - safe to dequeue and attempt to run
                task_id = await self.queue.dequeue_task(
                    timeout=config.WORKER_QUEUE_TIMEOUT_SECONDS
                )
                
                if task_id:
                    await self._process_task(task_id)
                
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(1)
        
        logger.info("Processing loop exited")
    
    async def _run_cleanup_loop(self) -> None:
        """Periodic cleanup loop - mark stale running tasks as failed."""
        logger.info("Cleanup loop started")
        
        while self.running:
            try:
                # Wait for cleanup interval
                await asyncio.sleep(config.WORKER_CLEANUP_INTERVAL_SECONDS)
                
                if not self.running:
                    break
                
                # Run cleanup
                logger.info("Running periodic stale task cleanup...")
                failed_count = await self.queue.cleanup_stale_running_tasks()
                
                if failed_count > 0:
                    logger.warning(f"Cleanup marked {failed_count} stale tasks as failed")
                else:
                    logger.debug("Cleanup found no stale tasks")
                
            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                # Continue running despite errors
                await asyncio.sleep(60)  # Wait a bit before retrying
        
        logger.info("Cleanup loop exited")
    
    async def _process_task(self, task_id: str) -> None:
        """Process a single backtest task.
        
        Args:
            task_id: Task to process
        """
        logger.info(f"Processing task {task_id}")
        lock_acquired = False
        
        try:
            # Retrieve task data
            task_data = await self.queue.get_task(task_id)
            if not task_data:
                logger.error(f"Task {task_id} not found in Redis")
                return
            
            # Acquire distributed lock
            lock_acquired = await self.queue.acquire_backtest_lock(task_id)
            
            if not lock_acquired:
                # Another worker is running a backtest, re-queue this task
                logger.info(f"Could not acquire lock for task {task_id}, re-queuing")
                await self.queue.enqueue_task(task_id)
                # Wait a bit before next iteration to avoid tight loop
                await asyncio.sleep(2)
                return
            
            # Update status to running
            await self.queue.update_task(task_id, {
                "status": "running",
                "started_at": datetime.now(datetime.timezone.utc).isoformat()
            })
            logger.info(f"Task {task_id} status: running")
            
            # Parse configuration
            config_dict = json.loads(task_data["config_json"])
            
            # Convert date strings back to date objects
            if "start_date" in config_dict and config_dict["start_date"]:
                from datetime import date
                config_dict["start_date"] = date.fromisoformat(config_dict["start_date"])
            if "end_date" in config_dict and config_dict["end_date"]:
                from datetime import date
                config_dict["end_date"] = date.fromisoformat(config_dict["end_date"])
            
            config = BacktestConfig(**config_dict)
            strategy_code = task_data["strategy_code"]
            
            # Execute backtest in thread pool (blocking I/O operation)
            logger.info(f"Starting backtest execution for task {task_id}")
            result = await asyncio.to_thread(
                self.orchestrator.backtest_strategy_from_code,
                strategy_code=strategy_code,
                config=config,
                base_dir=self.base_dir,
                task_id=task_id
            )
            logger.info(f"Backtest execution completed for task {task_id}")
            
            # Update task with results
            status = "complete" if result.get("success") else "failed"
            
            updates = {
                "status": status,
                "success": result.get("success", False),
                "strategy_path": result.get("strategy_path", ""),
                "results_file": result.get("results_file", ""),
                "tearsheet_file": result.get("tearsheet_file", ""),
                "error_message": result.get("error_message", ""),
                "completed_at": datetime.now(datetime.timezone.utc).isoformat()
            }
            
            await self.queue.update_task(task_id, updates)
            logger.info(f"Task {task_id} status: {status}")
            
            if not result.get("success"):
                logger.error(f"Task {task_id} failed: {result.get('error_message')}")
            
        except Exception as e:
            # Catch all exceptions to ensure task is marked as failed
            error_msg = f"Worker error: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"Task {task_id} failed with exception: {error_msg}")
            
            try:
                await self.queue.update_task(task_id, {
                    "status": "failed",
                    "success": False,
                    "error_message": error_msg,
                    "completed_at": datetime.now(datetime.timezone.utc).isoformat()
                })
            except Exception as update_error:
                logger.error(f"Failed to update task {task_id} status: {update_error}")
        
        finally:
            # Always release the lock
            if lock_acquired:
                try:
                    await self.queue.release_backtest_lock(task_id)
                except Exception as e:
                    logger.error(f"Failed to release lock for task {task_id}: {e}")
