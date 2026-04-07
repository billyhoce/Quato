"""Shared tool implementations for Zipline/Pipeline API docs and QuantRocket universe management.

These are plain functions (no MCP registration) so they can be imported and
registered by both the internal stdio server (quato_server.py) and the external
HTTP server (external_server.py).
"""
import asyncio
import json
import uuid
from datetime import date as _date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from quantrocket import master

from models.backtest_models import (
    BacktestConfig,
    TaskRecord,
    TaskStatus,
    US_FREE_STOCK_BUNDLE_DAILY,
)

# ---------------------------------------------------------------------------
# API documentation data
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PIPELINE_API_FILE = SCRIPT_DIR / "pipeline_api_parsed.json"
ZIPLINE_API_FILE = SCRIPT_DIR / "zipline_api_parsed.json"

with open(PIPELINE_API_FILE, "r", encoding="utf-8") as f:
    pipeline_api_data = json.load(f)

with open(ZIPLINE_API_FILE, "r", encoding="utf-8") as f:
    zipline_api_data = json.load(f)

combined_api_data = {**pipeline_api_data, **zipline_api_data}


def _extract_categories(api_data: dict, api_type: str) -> list[str]:
    """Extract unique category slugs from API data keys."""
    categories = set()
    prefix = f"docs/{api_type}/"
    for key in api_data:
        if key.startswith(prefix):
            rest = key[len(prefix):]
            slug = rest.split("/", 1)[0]
            categories.add(slug)
    return sorted(categories)


ZIPLINE_CATEGORIES = _extract_categories(zipline_api_data, "zipline")
PIPELINE_CATEGORIES = _extract_categories(pipeline_api_data, "pipeline")


# ---------------------------------------------------------------------------
# Shared tool functions
# ---------------------------------------------------------------------------

def get_functions_in_category(api_type: str, category_slug: str) -> dict[str, str]:
    """Get all function/class names and their descriptions in a specific category.

    Args:
        api_type: Either "zipline" or "pipeline"
        category_slug: The category slug (e.g., "built-in-factors", "assets", "scheduling-functions")

    Returns:
        Dict mapping function keys to their short descriptions.

    Example:
        get_functions_in_category("pipeline", "built-in-factors")
        Returns: {
            "docs/pipeline/built-in-factors/factors-dailyreturns": "Calculate daily returns...",
            "docs/pipeline/built-in-factors/factors-rsi": "Compute RSI indicator...",
            ...
        }
    """
    api_data = pipeline_api_data if api_type == "pipeline" else zipline_api_data
    category_prefix = f"docs/{api_type}/{category_slug}/"
    return {
        func_key: func_data.get("description", "No description available.")
        for func_key, func_data in api_data.items()
        if func_key.startswith(category_prefix)
    }


def get_function_or_class_details(function_class_names: list[str]) -> list[dict[str, Any]]:
    """Given a list of function or class names
       (E.g ["docs/pipeline/built-in-factors/factors-dailyreturns", "docs/zipline/fee-models/set-borrow-fees-provider"]),
       retrieve their detailed information, including description and parameters."""
    return [
        combined_api_data[name]
        for name in function_class_names
        if name in combined_api_data
    ]


def list_universes() -> dict[str, int]:
    """List all existing QuantRocket universes and the number of securities in each.

    Call this before creating a new universe or before writing a strategy that
    references a named universe, to see what already exists.

    Returns
    -------
    dict
        Mapping of universe name to security count,
        e.g. {"us-stocks": 8000, "tech-stocks": 420}.
    """
    return master.list_universes()


def search_securities(
    exchanges: list[str] | None = None,
    sec_types: list[str] | None = None,
    symbols: list[str] | None = None,
    universes: list[str] | None = None,
    exclude_delisted: bool = True,
    max_results: int = 200,
) -> list[dict[str, str | None]]:
    """Search the QuantRocket securities master for securities matching the given criteria.

    Use this to find the SIDs needed to build a universe, or to explore what
    securities are available before writing a strategy.

    - Known `sec_types` values in this deployment:
        "Common Stock"       — ordinary common shares (6 192 active)
        "Mutual Fund"        — ETFs and mutual funds (2 278); despite the name,
                               this category includes ETFs (e.g. SPY, QQQ).
                               Use this value to find ETFs.
        "Preferred Stock"    — preferred shares (1 214)
        "Depositary Receipt" — ADRs and similar (545)
        "REIT"               — real estate investment trusts (232)
        "Corp"               — corporate bond / trust certificates (170)
        "Warrant"            — warrants (138)
        "Equity"             — other equity instruments (131)
        "Partnership Shares" — LP units (104)
        "Unit"               — closed-end fund units, etc. (98)
      NOTE: "ETF" does NOT exist as a `sec_types` value — use
      "Mutual Fund" instead to find ETFs.

    Parameters
    ----------
    exchanges : list of str, optional
        Filter by exchange MIC codes (e.g. ["XNAS", "XNYS"] for NASDAQ / NYSE).
    sec_types : list of str, optional
        Security subtype filter. Use this to select asset classes reliably.
        e.g. ["Common Stock"], ["REIT"], ["Common Stock", "Depositary Receipt"].
    symbols : list of str, optional
        Filter to specific ticker symbols (e.g. ["AAPL", "MSFT"]).
    universes : list of str, optional
        Filter to securities already in these universes.
    exclude_delisted : bool
        Exclude delisted securities (default True).
    max_results : int
        Maximum number of results to return (default 200, hard-capped at 500).

    Returns
    -------
    list of dict
        Each dict has keys: sid, symbol
    """
    df = master.get_securities(
        exchanges=exchanges,
        symbols=symbols,
        universes=universes,
        exclude_delisted=exclude_delisted,
        fields=["Symbol", "Name", "usstock_SecurityType2"]
    )
    cap = min(max_results, 500)
    df = df.head(cap)

    result = []
    if sec_types:
        df = df[df["usstock_SecurityType2"].isin(sec_types)]
    for sid, row in df.iterrows():
        sym = row.get("Symbol")
        result.append({
            "sid": str(sid),
            "symbol": "" if pd.isna(sym) else str(sym)
        })
    return result


def create_universe(
    code: str,
    sids: list[str] | None = None,
    from_universes: list[str] | None = None,
    append: bool = False,
    replace: bool = False,
) -> dict[str, Any]:
    """Create a QuantRocket universe of securities.

    A universe is a named group of securities that can be used to scope a
    backtest or filter a Pipeline. Universe codes must be lowercase
    alphanumeric with hyphens only (e.g. "tech-stocks", "nyse-etfs").

    Typical workflow when building a universe from filters:
    1. Call search_securities with the desired criteria to get matching SIDs.
    2. Confirm the count looks right.
    3. Call create_universe with those SIDs and a descriptive code.

    Parameters
    ----------
    code : str
        Name for the universe (lowercase alphanumeric + hyphens).
    sids : list of str, optional
        Security IDs to include. Obtain these from search_securities.
    from_universes : list of str, optional
        Build the new universe from securities already in these existing
        universes (useful for creating a sub-universe).
    append : bool
        Append to universe if it already exists (default False).
    replace : bool
        Replace universe if it already exists (default False).

    Returns
    -------
    dict
        QuantRocket status: {"code": str, "provided": int, "inserted": int, "total_after_insert": int}
    """
    if not sids and not from_universes:
        raise ValueError(
            "Provide either 'sids' (a list of security IDs from search_securities) "
            "or 'from_universes'. Both are currently empty/None."
        )
    if sids is not None and len(sids) == 0:
        raise ValueError(
            "'sids' is an empty list. Call search_securities first to get security IDs, "
            "then pass the 'sid' values here."
        )
    return master.create_universe(
        code=code,
        sids=sids,
        from_universes=from_universes,
        append=append,
        replace=replace,
    )


# ---------------------------------------------------------------------------
# Shared backtest tool implementations
# ---------------------------------------------------------------------------

async def _submit_backtest_impl(
    queue,
    object_store,
    code: str,
    bundle: str,
    start_date: str,
    end_date: str,
    capital_base: float,
    session_id: str = "agent",
) -> dict:
    if queue is None:
        return {"error": "Backtest service not available"}

    backtest_config = BacktestConfig(
        bundle=bundle,
        start_date=_date.fromisoformat(start_date),
        end_date=_date.fromisoformat(end_date),
        capital_base=capital_base,
    )
    try:
        backtest_config.validate_config()
    except ValueError as e:
        return {"error": f"Invalid configuration: {e}"}

    task_id = str(uuid.uuid4())
    record = TaskRecord(
        task_id=task_id,
        session_id=session_id,
        status=TaskStatus.QUEUED,
        strategy_code=code,
        config_json=json.dumps(backtest_config.model_dump(mode="json")),
        created_at=datetime.now(timezone.utc),
    )

    await queue.create_task(record)
    await queue.add_to_session(session_id, task_id)
    await queue.enqueue_task(task_id)

    return {
        "task_id": task_id,
        "status": TaskStatus.QUEUED,
        "message": "Backtest queued. Poll get_backtest_status with this task_id.",
    }


async def _get_backtest_status_impl(queue, task_id: str) -> dict:
    if queue is None:
        return {"error": "Backtest service not available"}

    task = await queue.get_task(task_id)
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


async def _get_backtest_results_impl(queue, object_store, task_id: str) -> dict:
    if queue is None or object_store is None:
        return {"error": "Backtest service not available"}

    task = await queue.get_task(task_id)
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
            object_store.get_presigned_download_url, task.csv_object_key
        )

    if task.tearsheet_object_key:
        result["tearsheet_url"] = await asyncio.to_thread(
            object_store.get_presigned_download_url, task.tearsheet_object_key
        )

    return result


def make_backtest_tools(queue, object_store):
    """Return (submit_backtest, get_backtest_status, get_backtest_results) bound to queue/store.

    Used by quato_server.py (stdio) to register backtest tools at lifespan start
    when the queue connection is available.
    """

    async def submit_backtest(
        code: str,
        bundle: str = US_FREE_STOCK_BUNDLE_DAILY,
        start_date: str = "2008-01-01",
        end_date: str = "2011-12-31",
        capital_base: float = 100000.0,
        session_id: str = "agent",
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
        session_id : str
            Session identifier for grouping backtests (pass the current session ID).

        Returns
        -------
        dict
            {"task_id": str, "status": "queued", "message": str}
        """
        return await _submit_backtest_impl(
            queue, object_store, code, bundle, start_date, end_date, capital_base, session_id
        )

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
        return await _get_backtest_status_impl(queue, task_id)

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
        return await _get_backtest_results_impl(queue, object_store, task_id)

    return submit_backtest, get_backtest_status, get_backtest_results
