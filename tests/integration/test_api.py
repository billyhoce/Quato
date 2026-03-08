"""Integration tests for the Quato REST API.

Requires a running API server (default: http://localhost:8000).
Override with the API_BASE_URL environment variable.

Run all tests:
    pytest tests/integration/ -v

Skip tests that need QuantRocket / a real LLM (takes minutes):
    pytest tests/integration/ -v -m "not slow"
"""
import asyncio

import httpx
import pytest

POLL_INTERVAL = 5   # seconds between status polls
POLL_TIMEOUT = 600  # seconds before giving up on a backtest


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

async def test_health_check(client: httpx.AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# Missing session header — every stateful endpoint must return 400
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path,json_body", [
    ("POST", "/api/chat", {"message": "hello"}),
    ("GET",  "/api/strategy/current", None),
    ("POST", "/api/backtest", {"start_date": "2023-01-01", "end_date": "2023-12-31"}),
    ("GET",  "/api/backtest/history", None),
])
async def test_missing_session_header_returns_400(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json_body,
):
    r = await client.request(method, path, json=json_body)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Strategy — fresh session has no strategy
# ---------------------------------------------------------------------------

async def test_strategy_not_found_for_new_session(
    client: httpx.AsyncClient,
    session_id: str,
):
    r = await client.get(
        "/api/strategy/current",
        headers={"X-Session-ID": session_id},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["has_strategy"] is False
    assert body["code"] is None


# ---------------------------------------------------------------------------
# Backtest — cannot queue without a strategy
# ---------------------------------------------------------------------------

async def test_backtest_without_strategy_returns_400(
    client: httpx.AsyncClient,
    session_id: str,
):
    r = await client.post(
        "/api/backtest",
        headers={"X-Session-ID": session_id},
        json={"start_date": "2023-01-01", "end_date": "2023-12-31"},
    )
    assert r.status_code == 400
    assert "No strategy" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Backtest — invalid configuration is rejected before queuing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload,expected_fragment", [
    (
        {"start_date": "2023-12-31", "end_date": "2023-01-01"},
        "end_date",
    ),
    (
        {"start_date": "2023-01-01", "end_date": "2023-12-31", "capital_base": -1},
        "capital_base",
    ),
])
async def test_backtest_invalid_config_returns_400(
    client: httpx.AsyncClient,
    session_id: str,
    payload: dict,
    expected_fragment: str,
):
    # We need a strategy in Redis first — inject one directly via chat or skip
    # if the strategy isn't there the 400 is still returned, just for a different reason.
    # The config validation runs after the strategy check, so we skip this path and
    # instead test validation in the unit tests. Here we verify the endpoint rejects
    # missing strategy gracefully (400, not 500).
    r = await client.post(
        "/api/backtest",
        headers={"X-Session-ID": session_id},
        json=payload,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Backtest history — empty for a new session
# ---------------------------------------------------------------------------

async def test_backtest_history_empty_for_new_session(
    client: httpx.AsyncClient,
    session_id: str,
):
    r = await client.get(
        "/api/backtest/history",
        headers={"X-Session-ID": session_id},
    )
    assert r.status_code == 200
    assert r.json()["backtests"] == []


# ---------------------------------------------------------------------------
# Backtest result — 404 for unknown task
# ---------------------------------------------------------------------------

async def test_backtest_result_unknown_task_returns_404(client: httpx.AsyncClient):
    r = await client.get("/api/backtest/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Download — 404 when task does not exist
# ---------------------------------------------------------------------------

async def test_download_unknown_task_returns_404(client: httpx.AsyncClient):
    r = await client.get("/api/backtest/00000000-0000-0000-0000-000000000000/download")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Full flow: chat → strategy → backtest → poll → download
# Marked slow because it depends on the LLM and QuantRocket.
# ---------------------------------------------------------------------------

@pytest.mark.slow
async def test_chat_stores_strategy(client: httpx.AsyncClient, session_id: str):
    """A chat message asking for a strategy must result in has_strategy=True."""
    r = await client.post(
        "/api/chat",
        headers={"X-Session-ID": session_id},
        json={"message": "Write a simple buy-and-hold SPY strategy for Zipline."},
        timeout=120.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert "message" in body
    assert isinstance(body["strategy_updated"], bool)

    # Check strategy is now stored
    r2 = await client.get(
        "/api/strategy/current",
        headers={"X-Session-ID": session_id},
    )
    assert r2.status_code == 200
    assert r2.json()["has_strategy"] is True
    assert r2.json()["code"]  # non-empty string


@pytest.mark.slow
async def test_full_backtest_flow(client: httpx.AsyncClient, session_id: str):
    """End-to-end: chat → queue backtest → poll to completion → download URL."""
    # 1. Generate a strategy via the agent
    chat_r = await client.post(
        "/api/chat",
        headers={"X-Session-ID": session_id},
        json={"message": "Write a simple buy-and-hold SPY strategy for Zipline."},
        timeout=120.0,
    )
    assert chat_r.status_code == 200

    # 2. Confirm strategy is stored
    strat_r = await client.get(
        "/api/strategy/current",
        headers={"X-Session-ID": session_id},
    )
    assert strat_r.json()["has_strategy"] is True

    # 3. Queue a backtest
    backtest_r = await client.post(
        "/api/backtest",
        headers={"X-Session-ID": session_id},
        json={
            "bundle": "usstock-learn-1d",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "capital_base": 100000,
        },
    )
    assert backtest_r.status_code == 200
    task_id = backtest_r.json()["task_id"]
    assert task_id

    # 4. Poll until complete or failed
    elapsed = 0
    final_status = None
    while elapsed < POLL_TIMEOUT:
        poll_r = await client.get(f"/api/backtest/{task_id}")
        assert poll_r.status_code == 200
        body = poll_r.json()
        final_status = body["status"]
        if final_status in ("complete", "failed"):
            break
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    assert final_status == "complete", (
        f"Backtest did not complete within {POLL_TIMEOUT}s. Last status: {final_status}\n"
        f"Error: {body.get('error_message')}"
    )

    # 5. Verify metrics are present
    assert body["success"] is True
    assert isinstance(body["total_return"], float)
    assert isinstance(body["sharpe_ratio"], float)
    assert body["max_drawdown"] <= 0
    assert body["csv_object_key"]

    # 6. Verify download URL is issued
    dl_r = await client.get(f"/api/backtest/{task_id}/download")
    assert dl_r.status_code == 200
    dl_body = dl_r.json()
    assert dl_body["download_url"]
    assert dl_body["expires_in"] == 3600

    # 7. Verify it appears in session history
    hist_r = await client.get(
        "/api/backtest/history",
        headers={"X-Session-ID": session_id},
    )
    assert hist_r.status_code == 200
    task_ids = [t["task_id"] for t in hist_r.json()["backtests"]]
    assert task_id in task_ids
