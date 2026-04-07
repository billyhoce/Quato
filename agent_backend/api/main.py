"""FastAPI application for Quato strategy coder."""
import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

import config
from agent_backend.mcp_server.external_server import mcp as external_mcp, set_services as set_mcp_services

# Build the MCP ASGI sub-app once so we can wire its lifespan into ours
_mcp_http_app = external_mcp.http_app(path="/")
from backtesting.models.backtest_models import (
    BacktestConfig,
    TaskRecord,
    TaskStatus,
    US_FREE_STOCK_BUNDLE_DAILY,
)
from agent_backend.agent.agent_service import AgentService
from agent_backend.agent.strategy_manager import StrategyManager
from backtesting.queue.backtest_queue import BacktestQueue
from backtesting.queue.backtest_worker import BacktestWorker
from backtesting.storage.object_store import ObjectStoreService

# Load environment variables from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Configure logging
log_file = Path(__file__).parent.parent.parent / "coder_agent.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler(log_file, mode='a')  # File output
    ]
)
logger = logging.getLogger(__name__)

# Global services
strategy_manager = StrategyManager()
agent_service = AgentService(strategy_manager)
backtest_queue = BacktestQueue()
object_store = ObjectStoreService()
backtest_worker: Optional[BacktestWorker] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    global backtest_worker

    async with _mcp_http_app.lifespan(app):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        logger.info("Initializing services...")

        # Ensure the object store bucket exists (synchronous boto3 call)
        await asyncio.to_thread(object_store.ensure_bucket)

        # AsyncRedisSaver owns the connection for LangGraph conversation checkpoints.
        async with AsyncRedisSaver.from_conn_string(redis_url) as checkpointer:
            await agent_service.initialize(checkpointer)

            await strategy_manager.connect()
            await backtest_queue.connect()

            failed_count = await backtest_queue.mark_running_as_failed()
            if failed_count > 0:
                logger.info(f"Marked {failed_count} orphaned tasks as failed")

            base_dir = Path(__file__).parent.parent.parent
            backtest_worker = BacktestWorker(
                queue=backtest_queue,
                base_dir=base_dir,
                object_store=object_store,
            )
            await backtest_worker.start()

            set_mcp_services(backtest_queue, object_store)
            logger.info("API ready!")

            yield

            logger.info("Shutting down...")

            if backtest_worker:
                await backtest_worker.stop()

            await strategy_manager.close()
            await backtest_queue.close()


app = FastAPI(
    title="Quato Strategy Coder API",
    description="API for AI-powered trading strategy generation and backtesting",
    version="1.0.0",
    lifespan=lifespan
)

# Mount external MCP server for web Claude users
app.mount("/mcp", _mcp_http_app)

_MCP_API_KEY = os.getenv("MCP_API_KEY")


@app.middleware("http")
async def mcp_auth_middleware(request: Request, call_next):
    if request.url.path.startswith("/mcp") and _MCP_API_KEY:
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").removeprefix("Bearer ")
        if api_key != _MCP_API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)

# CORS — allow frontend dev server and any configured origins
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    message: str
    strategy_updated: bool
    strategy_code: Optional[str] = None
    error: Optional[str] = None


class StrategyResponse(BaseModel):
    code: Optional[str]
    has_strategy: bool


class StrategySummaryResponse(BaseModel):
    summary: Optional[str] = None
    title: Optional[str] = None
    has_strategy: bool


class BacktestRequest(BaseModel):
    bundle: str = US_FREE_STOCK_BUNDLE_DAILY
    start_date: Optional[date] = date(2008, 1, 1)
    end_date: Optional[date] = date(2011, 12, 31)
    capital_base: Optional[float] = 100000


class BacktestResponse(BaseModel):
    task_id: str
    status: str
    message: str


class BacktestResultResponse(BaseModel):
    task_id: str
    status: str
    success: Optional[bool] = None
    error_message: Optional[str] = None
    csv_object_key: Optional[str] = None
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    execution_time: Optional[float] = None


class BacktestDownloadResponse(BaseModel):
    download_url: str
    expires_in: int


class BacktestHistoryResponse(BaseModel):
    backtests: List[dict]


class UniverseItem(BaseModel):
    name: str
    security_count: int


class UniverseListResponse(BaseModel):
    universes: List[UniverseItem]


class SecurityItem(BaseModel):
    sid: str
    symbol: str
    name: Optional[str]
    security_type: Optional[str]
    exchange: Optional[str]


class UniverseSecuritiesResponse(BaseModel):
    universe_name: str
    securities: List[SecurityItem]
    total_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_session_id: str = Header(default=None)
):
    """Send a message to the agent and get a response."""
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")

    try:
        result = await agent_service.chat(x_session_id, request.message)
        return ChatResponse(**result)
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategy/current", response_model=StrategyResponse)
async def get_current_strategy(
    x_session_id: str = Header(default=None)
):
    """Get the current strategy code for the session."""
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")

    code = await strategy_manager.get_strategy(x_session_id)
    return StrategyResponse(code=code, has_strategy=code is not None)


@app.get("/api/strategy/summary", response_model=StrategySummaryResponse)
async def get_strategy_summary(
    x_session_id: str = Header(default=None)
):
    """Get an LLM-generated plain-English summary of the current strategy."""
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")

    code = await strategy_manager.get_strategy(x_session_id)
    if not code:
        return StrategySummaryResponse(summary=None, has_strategy=False)

    try:
        summary, title = await asyncio.gather(
            strategy_manager.get_or_create_summary(x_session_id, code),
            strategy_manager.get_or_create_title(x_session_id, code),
        )
        return StrategySummaryResponse(summary=summary, title=title, has_strategy=True)
    except Exception as e:
        logger.error(f"Summary generation error: {e}", exc_info=True)
        return StrategySummaryResponse(summary=None, title=None, has_strategy=True)


@app.post("/api/backtest", response_model=BacktestResponse)
async def start_backtest(
    request: BacktestRequest,
    x_session_id: str = Header(default=None)
):
    """Queue the current strategy for backtesting.

    Returns immediately with a task_id to poll for results.
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Session ID required")

    if not await strategy_manager.has_strategy(x_session_id):
        raise HTTPException(status_code=400, detail="No strategy found for session")

    strategy_code = await strategy_manager.get_strategy(x_session_id)

    backtest_config = BacktestConfig(
        bundle=request.bundle,
        start_date=request.start_date,
        end_date=request.end_date,
        capital_base=request.capital_base,
        # filepath_or_buffer left None; set by the orchestrator before the run
    )

    try:
        backtest_config.validate_config()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid configuration: {e}")

    task_id = str(uuid.uuid4())

    record = TaskRecord(
        task_id=task_id,
        session_id=x_session_id,
        status=TaskStatus.QUEUED,
        strategy_code=strategy_code,
        config_json=json.dumps(backtest_config.model_dump(mode="json")),
        created_at=datetime.now(timezone.utc),
    )

    try:
        await backtest_queue.create_task(record)
        await backtest_queue.add_to_session(x_session_id, task_id)
        await backtest_queue.enqueue_task(task_id)
        logger.info(f"Queued backtest task {task_id} for session {x_session_id}")

        return BacktestResponse(
            task_id=task_id,
            status=TaskStatus.QUEUED,
            message="Backtest queued successfully",
        )
    except Exception as e:
        logger.error(f"Failed to queue backtest: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to queue backtest: {e}")


# /history must be defined before /{task_id} to prevent FastAPI route shadowing
@app.get("/api/backtest/history", response_model=BacktestHistoryResponse)
async def get_backtest_history():
    """Return all backtests across all sessions, newest first."""
    tasks = await backtest_queue.get_all_tasks()
    return BacktestHistoryResponse(backtests=[
        {
            "task_id": t.task_id,
            "status": t.status,
            "session_id": t.session_id,
            "created_at": t.created_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "success": t.success,
            "total_return": t.total_return,
            "sharpe_ratio": t.sharpe_ratio,
            "max_drawdown": t.max_drawdown,
            "execution_time": t.execution_time,
            "error_message": t.error_message,
        }
        for t in tasks
    ])


@app.get("/api/backtest/{task_id}", response_model=BacktestResultResponse)
async def get_backtest_result(task_id: str):
    """Get the status and results of a backtest."""
    task = await backtest_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Backtest not found")

    return BacktestResultResponse(
        task_id=task.task_id,
        status=task.status,
        success=task.success,
        error_message=task.error_message,
        csv_object_key=task.csv_object_key,
        total_return=task.total_return,
        sharpe_ratio=task.sharpe_ratio,
        max_drawdown=task.max_drawdown,
        execution_time=task.execution_time,
    )


@app.get("/api/backtest/{task_id}/download", response_model=BacktestDownloadResponse)
async def get_backtest_download(task_id: str):
    """Generate a pre-signed URL for direct download of the backtest results CSV.

    The URL is valid for 1 hour and can be used by the client without
    further authentication — suitable for passing directly to a download link
    or a pandas read_csv() call.
    """
    task = await backtest_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Backtest not found")
    if not task.csv_object_key:
        raise HTTPException(
            status_code=404,
            detail=(
                "No CSV available for this backtest "
                "(still running, or failed before upload)"
            ),
        )

    url = await asyncio.to_thread(
        object_store.get_presigned_download_url, task.csv_object_key
    )
    return BacktestDownloadResponse(download_url=url, expires_in=3600)


@app.get("/api/backtest/{task_id}/tearsheet", response_model=BacktestDownloadResponse)
async def get_backtest_tearsheet(task_id: str):
    """Generate a pre-signed URL for direct download of the backtest tear sheet PDF.

    The URL is valid for 1 hour.
    """
    task = await backtest_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Backtest not found")
    if not task.tearsheet_object_key:
        raise HTTPException(
            status_code=404,
            detail=(
                "No tear sheet available for this backtest "
                "(still running, failed, or tear sheet generation failed)"
            ),
        )

    url = await asyncio.to_thread(
        object_store.get_presigned_download_url, task.tearsheet_object_key
    )
    return BacktestDownloadResponse(download_url=url, expires_in=3600)


@app.get("/api/universes", response_model=UniverseListResponse)
async def list_universes():
    """Return all QuantRocket universes with their security counts."""
    import quantrocket.master as qr_master
    universe_counts: dict = await asyncio.to_thread(qr_master.list_universes)
    universes = [
        UniverseItem(name=name, security_count=count)
        for name, count in universe_counts.items()
    ]
    return UniverseListResponse(universes=universes)


@app.get("/api/universes/{name}/securities", response_model=UniverseSecuritiesResponse)
async def get_universe_securities(name: str):
    """Return securities in a QuantRocket universe (capped at 500)."""
    import quantrocket.master as qr_master
    df = await asyncio.to_thread(
        qr_master.get_securities,
        universes=[name],
        fields=["Symbol", "Name", "usstock_SecurityType2", "Exchange"],
    )
    total_count = len(df)
    df = df.head(500)

    securities = [
        SecurityItem(
            sid=str(sid),
            symbol=row.get("Symbol") or "",
            name=row.get("Name"),
            security_type=row.get("usstock_SecurityType2"),
            exchange=row.get("Exchange"),
        )
        for sid, row in df.iterrows()
    ]
    return UniverseSecuritiesResponse(
        universe_name=name,
        securities=securities,
        total_count=total_count,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Quato Strategy Coder API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
