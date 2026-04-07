"""External MCP server for web Claude users.

Exposes all Zipline/Pipeline API doc tools plus backtest submission and
status tools over HTTP (streamable-http transport), mounted in FastAPI at /mcp.
"""
import json

from fastmcp import FastMCP

from agent_backend.mcp_server.tools import (
    ZIPLINE_CATEGORIES,
    PIPELINE_CATEGORIES,
    get_functions_in_category,
    get_function_or_class_details,
    list_universes,
    search_securities,
    create_universe,
    _submit_backtest_impl,
    _get_backtest_results_impl,
    _wait_for_backtest_impl,
    US_FREE_STOCK_BUNDLE_DAILY,
)

mcp = FastMCP("QuatoExternal")

# ---------------------------------------------------------------------------
# Service injection — called from agent_backend/api/main.py lifespan after init
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
def get_zipline_categories() -> str:
    """Retrieve the available category slugs in the Zipline API.

    Use the get_functions_in_category tool with api_type="zipline" and a category slug to see functions in that category.
    """
    return json.dumps(ZIPLINE_CATEGORIES)


@mcp.resource("ziplineApi://pipeline_categories")
def get_pipeline_categories() -> str:
    """Retrieve the available category slugs in the Pipeline API.

    Use the get_functions_in_category tool with api_type="pipeline" and a category slug to see functions in that category.
    """
    return json.dumps(PIPELINE_CATEGORIES)


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
    session_id: str = "agent",
) -> dict:
    """Submit Zipline strategy Python code for backtesting.

    Enqueues the strategy for execution and returns a task_id. Call
    wait_for_backtest immediately after to block until the backtest completes.

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
    session_id : str
        Session identifier for grouping backtests (pass the current session ID).

    Returns
    -------
    dict
        {"task_id": str, "status": "queued", "message": str}
    """
    return await _submit_backtest_impl(
        _backtest_queue, _object_store, code, bundle, start_date, end_date, capital_base, session_id
    )


@mcp.tool()
async def wait_for_backtest(task_id: str, timeout_seconds: int = 300) -> dict:
    """Wait for a submitted backtest to finish and return its full results.

    Blocks server-side until the backtest completes or fails, or until
    timeout_seconds elapses. If it times out, call this tool again with the
    same task_id to keep waiting — the backtest continues running.

    Parameters
    ----------
    task_id : str
        The task_id returned by submit_backtest.
    timeout_seconds : int
        How long to wait before returning a timeout response (default 300s).

    Returns
    -------
    dict
        On success: full results including total_return, sharpe_ratio,
        max_drawdown, execution_time_seconds, csv_url, tearsheet_url.
        On failure: status="failed" and error_message.
        On timeout: status="pending" and a message to call again.
    """
    return await _wait_for_backtest_impl(
        _backtest_queue, _object_store, task_id, timeout_seconds
    )


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
    return await _get_backtest_results_impl(_backtest_queue, _object_store, task_id)
