"""FastAPI application for Quato strategy coder."""
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional
from datetime import date

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from services.agent_service import AgentService
from services.strategy_manager import StrategyManager
from backtesting_orchestrator.orchestrator import BacktestingOrchestrator
from models.backtest_models import BacktestConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global services
strategy_manager = StrategyManager()
agent_service = AgentService(strategy_manager)
backtest_orchestrator = BacktestingOrchestrator()

# Backtest tracking (in-memory for now)
backtest_results: Dict[str, dict] = {}
session_backtest_history: Dict[str, List[str]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup."""
    logger.info("Initializing AgentService...")
    await agent_service.initialize()
    logger.info("API ready!")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Quato Strategy Coder API",
    description="API for AI-powered trading strategy generation and backtesting",
    version="1.0.0",
    lifespan=lifespan
)

# Request/Response Models
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


class BacktestRequest(BaseModel):
    start_date: Optional[date] = date(2023, 1, 1)
    end_date: Optional[date] = date(2023, 12, 31)
    capital_base: Optional[float] = 100000


class BacktestResponse(BaseModel):
    task_id: str
    status: str  # "queued", "running", "complete", "failed"
    message: str


class BacktestResultResponse(BaseModel):
    task_id: str
    status: str
    success: Optional[bool] = None
    strategy_path: Optional[str] = None
    results_file: Optional[str] = None
    tearsheet_file: Optional[str] = None
    error_message: Optional[str] = None


class BacktestHistoryResponse(BaseModel):
    backtests: List[dict]


# Endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_session_id: str = Header(default=None)
):
    """Send a message to the agent and get a response.
    
    The agent may update the strategy based on the conversation.
    """
    if not x_session_id:
        x_session_id = str(uuid.uuid4())
        logger.info(f"Generated new session ID: {x_session_id}")
    
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
        return StrategyResponse(code=None, has_strategy=False)
    
    code = strategy_manager.get_strategy(x_session_id)
    return StrategyResponse(
        code=code,
        has_strategy=code is not None
    )


@app.post("/api/backtest", response_model=BacktestResponse)
async def start_backtest(
    request: BacktestRequest,
    x_session_id: str = Header(default=None)
):
    """Start a backtest with the current strategy.
    
    Returns a task_id to poll for results.
    """
    if not x_session_id:
        raise HTTPException(status_code=400, detail="Session ID required")
    
    # Check if strategy exists
    if not strategy_manager.has_strategy(x_session_id):
        raise HTTPException(status_code=400, detail="No strategy found for session")
    
    strategy_code = strategy_manager.get_strategy(x_session_id)
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Store initial status
    backtest_results[task_id] = {
        "status": "running",
        "session_id": x_session_id
    }
    
    # Track in session history
    if x_session_id not in session_backtest_history:
        session_backtest_history[x_session_id] = []
    session_backtest_history[x_session_id].append(task_id)
    
    # Run backtest asynchronously (for now, run synchronously)
    # In production, use Celery or similar for true async execution
    try:
        base_dir = Path(__file__).parent.parent
        config = BacktestConfig(
            start_date=request.start_date,
            end_date=request.end_date,
            capital_base=request.capital_base,
            filepath_or_buffer=None
        )
        
        result = backtest_orchestrator.backtest_strategy_from_code(
            strategy_code=strategy_code,
            config=config,
            base_dir=base_dir
        )
        
        # Update result
        backtest_results[task_id].update({
            "status": "complete" if result["success"] else "failed",
            **result
        })
        
        return BacktestResponse(
            task_id=task_id,
            status=backtest_results[task_id]["status"],
            message="Backtest completed" if result["success"] else "Backtest failed"
        )
        
    except Exception as e:
        logger.error(f"Backtest error: {str(e)}", exc_info=True)
        backtest_results[task_id] = {
            "status": "failed",
            "error_message": str(e),
            "session_id": x_session_id
        }
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/backtest/{task_id}", response_model=BacktestResultResponse)
async def get_backtest_result(task_id: str):
    """Get the status and results of a backtest."""
    if task_id not in backtest_results:
        raise HTTPException(status_code=404, detail="Backtest not found")
    
    result = backtest_results[task_id]
    return BacktestResultResponse(task_id=task_id, **result)


@app.get("/api/backtest/history", response_model=BacktestHistoryResponse)
async def get_backtest_history(
    x_session_id: str = Header(default=None)
):
    """Get all backtests for the current session."""
    if not x_session_id or x_session_id not in session_backtest_history:
        return BacktestHistoryResponse(backtests=[])
    
    task_ids = session_backtest_history[x_session_id]
    backtests = []
    
    for task_id in task_ids:
        if task_id in backtest_results:
            result = backtest_results[task_id].copy()
            result["task_id"] = task_id
            backtests.append(result)
    
    return BacktestHistoryResponse(backtests=backtests)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Quato Strategy Coder API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)