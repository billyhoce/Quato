"""External MCP server for web Claude users.

Exposes all Zipline/Pipeline API doc tools plus backtest submission and
status tools over HTTP (streamable-http transport), mounted in FastAPI at /mcp.

Internal agent uses quato_server.py (stdio) — this server is separate so
backtest tools are NOT accessible to the internal agent.
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastmcp import FastMCP

from mcp_server.tools import (
    ZIPLINE_CATEGORIES,
    PIPELINE_CATEGORIES,
    get_functions_in_category,
    get_function_or_class_details,
    list_universes,
    search_securities,
    create_universe,
)
from models.backtest_models import (
    BacktestConfig,
    TaskRecord,
    TaskStatus,
    US_FREE_STOCK_BUNDLE_DAILY,
)

mcp = FastMCP("QuatoExternal")

# ---------------------------------------------------------------------------
# Service injection — called from api/main.py lifespan after init
# ---------------------------------------------------------------------------

_backtest_queue = None
_object_store = None


def set_services(queue, store) -> None:
    """Inject shared service instances so MCP tools can use them."""
    global _backtest_queue, _object_store
    _backtest_queue = queue
    _object_store = store


# ---------------------------------------------------------------------------
# Shared resources
# ---------------------------------------------------------------------------

@mcp.resource("ziplineApi://zipline_categories")
def get_zipline_categories() -> list[str]:
    """Retrieve the available category slugs in the Zipline API.

    Use the get_functions_in_category tool with api_type="zipline" and a category slug to see functions in that category.
    """
    return ZIPLINE_CATEGORIES


@mcp.resource("ziplineApi://pipeline_categories")
def get_pipeline_categories() -> list[str]:
    """Retrieve the available category slugs in the Pipeline API.

    Use the get_functions_in_category tool with api_type="pipeline" and a category slug to see functions in that category.
    """
    return PIPELINE_CATEGORIES


# ---------------------------------------------------------------------------
# Shared tools (Zipline API docs + universe management)
# ---------------------------------------------------------------------------

mcp.tool(get_functions_in_category)
mcp.tool(get_function_or_class_details)
mcp.tool(list_universes)
mcp.tool(search_securities)
mcp.tool(create_universe)


# ---------------------------------------------------------------------------
# Backtest tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def submit_backtest(
    code: str,
    bundle: str = US_FREE_STOCK_BUNDLE_DAILY,
    start_date: str = "2008-01-01",
    end_date: str = "2011-12-31",
    capital_base: float = 100000.0,
) -> dict:
    """Submit Zipline strategy Python code for backtesting.

    Enqueues the strategy for execution and returns a task_id. Use
    get_backtest_status to poll until the backtest completes, then call
    get_backtest_results for full metrics and download links.

    Parameters
    ----------
    code : str
        Complete Zipline strategy Python source code.
    bundle : str
        Data bundle to use. Default is "usstock-learn-1d" (free daily US stocks).
    start_date : str
        Backtest start date in YYYY-MM-DD format (default "2008-01-01").
    end_date : str
        Backtest end date in YYYY-MM-DD format (default "2011-12-31").
    capital_base : float
        Starting capital in USD (default 100,000).

    Returns
    -------
    dict
        {"task_id": str, "status": "queued", "message": str}
    """
    if _backtest_queue is None:
        return {"error": "Backtest service not available"}

    from datetime import date
    backtest_config = BacktestConfig(
        bundle=bundle,
        start_date=date.fromisoformat(start_date),
        end_date=date.fromisoformat(end_date),
        capital_base=capital_base,
    )
    try:
        backtest_config.validate_config()
    except ValueError as e:
        return {"error": f"Invalid configuration: {e}"}

    task_id = str(uuid.uuid4())
    record = TaskRecord(
        task_id=task_id,
        session_id="mcp",
        status=TaskStatus.QUEUED,
        strategy_code=code,
        config_json=json.dumps(backtest_config.model_dump(mode="json")),
        created_at=datetime.now(timezone.utc),
    )

    await _backtest_queue.create_task(record)
    await _backtest_queue.add_to_session("mcp", task_id)
    await _backtest_queue.enqueue_task(task_id)

    return {
        "task_id": task_id,
        "status": TaskStatus.QUEUED,
        "message": "Backtest queued. Poll get_backtest_status with this task_id.",
    }


@mcp.tool()
async def get_backtest_status(task_id: str) -> dict:
    """Check the status of a submitted backtest.

    Poll this every 30–60 seconds after calling submit_backtest until
    status is "complete" or "failed".

    Parameters
    ----------
    task_id : str
        The task_id returned by submit_backtest.

    Returns
    -------
    dict
        Always includes "status" (queued/running/complete/failed).
        On completion also includes: total_return, sharpe_ratio, max_drawdown,
        execution_time (seconds).
        On failure includes: error_message.
    """
    if _backtest_queue is None:
        return {"error": "Backtest service not available"}

    task = await _backtest_queue.get_task(task_id)
    if task is None:
        return {"error": f"Task {task_id!r} not found"}

    result: dict = {"task_id": task.task_id, "status": task.status}

    if task.status == TaskStatus.COMPLETE:
        result.update({
            "total_return": task.total_return,
            "sharpe_ratio": task.sharpe_ratio,
            "max_drawdown": task.max_drawdown,
            "execution_time_seconds": task.execution_time,
        })
    elif task.status == TaskStatus.FAILED:
        result["error_message"] = task.error_message

    return result


@mcp.tool()
async def get_backtest_results(task_id: str) -> dict:
    """Get full results for a completed backtest, including download URLs.

    Only call this after get_backtest_status returns status="complete".

    Parameters
    ----------
    task_id : str
        The task_id returned by submit_backtest.

    Returns
    -------
    dict
        Performance metrics plus time-limited presigned URLs (valid 1 hour):
        - csv_url: direct download link for the full results CSV
        - tearsheet_url: direct download link for the PDF tear sheet (if available)
    """
    if _backtest_queue is None or _object_store is None:
        return {"error": "Backtest service not available"}

    task = await _backtest_queue.get_task(task_id)
    if task is None:
        return {"error": f"Task {task_id!r} not found"}

    if task.status != TaskStatus.COMPLETE:
        return {
            "task_id": task.task_id,
            "status": task.status,
            "message": "Backtest is not complete yet. Check status with get_backtest_status.",
        }

    result: dict = {
        "task_id": task.task_id,
        "status": task.status,
        "total_return": task.total_return,
        "sharpe_ratio": task.sharpe_ratio,
        "max_drawdown": task.max_drawdown,
        "execution_time_seconds": task.execution_time,
    }

    if task.csv_object_key:
        result["csv_url"] = await asyncio.to_thread(
            _object_store.get_presigned_download_url, task.csv_object_key
        )

    if task.tearsheet_object_key:
        result["tearsheet_url"] = await asyncio.to_thread(
            _object_store.get_presigned_download_url, task.tearsheet_object_key
        )

    return result
