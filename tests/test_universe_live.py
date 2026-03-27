"""
Live integration tests — run against a real QuantRocket server.

These tests verify that:
  1. The MCP tool functions call quantrocket with parameters it actually accepts.
  2. The agent generates valid quantrocket parameters from natural language prompts.

Requires:
  - HOUSTON_URL set (e.g. http://localhost:1969)
  - Securities master database populated in QuantRocket
  - ANTHROPIC_API_KEY set (for agent-level tests)
  - Redis running on REDIS_URL (or pass --no-redis to use MemorySaver)

Run:
  pytest tests/test_universe_live.py -v
  pytest tests/test_universe_live.py -v -k "not agent"   # tool tests only, no LLM cost
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Add project root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Defer quantrocket and quato_server imports until the session fixture has
# restored the real quantrocket module (in case unit tests injected a mock
# into sys.modules earlier in the same session).
qr_master = None
list_universes_fn = None
search_securities_fn = None
create_universe_fn = None

# ---------------------------------------------------------------------------
# Universe names created during this test run — cleaned up by session fixture
# ---------------------------------------------------------------------------
_CREATED_UNIVERSES: list[str] = []
_TEST_PREFIX = "quato-live-test"


def _test_universe(suffix: str) -> str:
    name = f"{_TEST_PREFIX}-{suffix}"
    _CREATED_UNIVERSES.append(name)
    return name


# ---------------------------------------------------------------------------
# Skip everything if HOUSTON_URL is not set
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not os.getenv("HOUSTON_URL"),
    reason="HOUSTON_URL not set — live QuantRocket tests skipped",
)


# ---------------------------------------------------------------------------
# Session fixture: reinstate real quantrocket, then clean up test universes.
#
# test_universe_mcp_tools.py injects a MagicMock into sys.modules at module
# load time.  When both files run in the same pytest session the mock leaks
# in here, so we must clear it and reload the real package first.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def setup_live_session():
    """Reload real quantrocket and bind module-level helpers."""
    global qr_master, list_universes_fn, search_securities_fn, create_universe_fn
    import importlib

    # Remove any mocked quantrocket injected by unit-test session mates
    for key in list(sys.modules):
        if key == "quantrocket" or key.startswith("quantrocket."):
            del sys.modules[key]

    # Load real quantrocket
    importlib.import_module("quantrocket")
    importlib.import_module("quantrocket.master")
    import quantrocket.master as _qr_master
    qr_master = _qr_master

    # Remove cached quato_server so the next import picks up the real quantrocket.
    # We must do this AFTER loading real quantrocket so sys.modules is clean.
    for key in list(sys.modules):
        if "quato_server" in key:
            del sys.modules[key]

    # Import quato_server fresh — it will resolve `from quantrocket import master`
    # against the real package now in sys.modules.
    import mcp_server.quato_server as _qs
    list_universes_fn = _qs.list_universes.fn
    search_securities_fn = _qs.search_securities.fn
    create_universe_fn = _qs.create_universe.fn

    yield

    # Cleanup: delete all test universes created during this session
    for code in _CREATED_UNIVERSES:
        try:
            qr_master.delete_universe(code)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Tool-level live tests  (no LLM, cheap to run)
# ---------------------------------------------------------------------------

class TestLiveListUniverses:
    def test_returns_dict(self):
        result = list_universes_fn()
        assert isinstance(result, dict), "list_universes must return a dict"

    def test_values_are_int_counts(self):
        result = list_universes_fn()
        for name, count in result.items():
            assert isinstance(name, str), f"Universe name must be str, got {type(name)}"
            assert isinstance(count, int), f"Count for '{name}' must be int, got {type(count)}"
            assert count >= 0


class TestLiveSearchSecurities:
    def test_returns_list(self):
        result = search_securities_fn(max_results=5)
        assert isinstance(result, list)

    def test_each_item_has_required_keys(self):
        result = search_securities_fn(max_results=5)
        for item in result:
            assert "sid" in item and item["sid"], "sid must be non-empty"
            assert "symbol" in item,              "symbol key required"
            assert "name" in item,                "name key required"
            assert "security_type" in item,        "security_type key required"
            assert "exchange" in item,             "exchange key required"

    def test_filter_by_sec_type_stk(self):
        result = search_securities_fn(sec_types=["STK"], max_results=20)
        assert len(result) > 0, "Expected at least one STK security"

    def test_filter_by_usstock_security_type2_mutual_fund(self):
        # ETFs are stored under usstock_SecurityType2="Mutual Fund" in this
        # deployment. Verify that filtering by "Mutual Fund" returns results.
        result = search_securities_fn(usstock_security_type2=["Mutual Fund"], max_results=20)
        assert isinstance(result, list), "search_securities must return a list"
        assert len(result) > 0, "Expected ETF/mutual-fund securities under usstock_SecurityType2='Mutual Fund'"
        types = {r["security_type"] for r in result}
        assert "Mutual Fund" in types, f"Expected 'Mutual Fund' in security_type values, got: {types}"

    def test_filter_by_symbols(self):
        result = search_securities_fn(symbols=["AAPL", "MSFT"], max_results=10)
        returned_symbols = {r["symbol"] for r in result}
        assert returned_symbols & {"AAPL", "MSFT"}, (
            f"Expected AAPL or MSFT in results, got: {returned_symbols}"
        )

    def test_max_results_respected(self):
        result = search_securities_fn(max_results=3)
        assert len(result) <= 3

    def test_sids_are_strings(self):
        result = search_securities_fn(max_results=10)
        for item in result:
            assert isinstance(item["sid"], str)

    def test_exclude_delisted_returns_active_securities(self):
        result = search_securities_fn(exclude_delisted=True, max_results=10)
        # Just verify we get results — QuantRocket would raise if the param were invalid
        assert isinstance(result, list)


class TestLiveCreateUniverse:
    def test_create_from_sids(self):
        # Get some real SIDs first
        securities = search_securities_fn(symbols=["AAPL", "MSFT", "GOOGL"], max_results=10)
        assert securities, "Need at least one security to create universe"

        sids = [s["sid"] for s in securities]
        code = _test_universe("symbols")

        result = create_universe_fn(code, sids=sids, replace=True)

        assert isinstance(result, dict), "create_universe must return a dict"
        # QuantRocket returns {"code": ..., "provided": ..., "inserted": ..., "total_after_insert": ...}
        assert "code" in result or "status" in result, (
            f"Expected 'code' or 'status' key in result, got: {result}"
        )

    def test_created_universe_appears_in_list(self):
        securities = search_securities_fn(symbols=["AAPL", "MSFT"], max_results=5)
        sids = [s["sid"] for s in securities]
        code = _test_universe("in-list")

        create_universe_fn(code, sids=sids, replace=True)

        universes = list_universes_fn()
        assert code in universes, (
            f"Universe '{code}' not found after creation. Got: {list(universes.keys())}"
        )

    def test_created_universe_has_correct_count(self):
        securities = search_securities_fn(symbols=["AAPL", "MSFT", "GOOGL"], max_results=10)
        sids = [s["sid"] for s in securities]
        code = _test_universe("count-check")

        create_universe_fn(code, sids=sids, replace=True)

        universes = list_universes_fn()
        assert universes[code] == len(sids), (
            f"Universe size mismatch: expected {len(sids)}, got {universes[code]}"
        )

    def test_create_from_existing_universe(self):
        # Depends on at least one universe existing
        existing = list_universes_fn()
        if not existing:
            pytest.skip("No existing universes to build from")

        source = next(iter(existing))
        code = _test_universe("from-existing")

        result = create_universe_fn(code, from_universes=[source], replace=True)
        assert isinstance(result, dict) and ("code" in result or "status" in result)

        universes = list_universes_fn()
        assert code in universes


# ---------------------------------------------------------------------------
# Agent-level live tests  (real LLM + real QuantRocket)
# ---------------------------------------------------------------------------

@pytest.fixture
def live_agent_chat(setup_live_session):
    """
    Per-test fixture: spins up a fresh AgentService, runs tests on its own
    event loop, then tears it down.  Keeping init and all chat calls on the
    SAME loop avoids "Event loop is closed" errors from asyncio resources
    (MCP client, checkpointer) being tied to a specific loop.
    """
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)

    from langgraph.checkpoint.memory import MemorySaver
    from services.agent_service import AgentService
    from services.strategy_manager import StrategyManager

    strategy_manager = StrategyManager()
    agent_service = AgentService(strategy_manager)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(strategy_manager.connect())
    loop.run_until_complete(agent_service.initialize(MemorySaver()))

    def chat(message: str) -> dict:
        session_id = f"live-{uuid.uuid4().hex[:8]}"
        return loop.run_until_complete(agent_service.chat(session_id, message))

    yield chat

    loop.run_until_complete(strategy_manager.close())
    loop.close()
    asyncio.set_event_loop(None)


class TestLiveAgentUniverseCreation:
    """
    Verify the agent produces quantrocket-valid parameters end-to-end.
    Each test sends a natural-language request and asserts the resulting
    universe actually exists in QuantRocket with a non-zero security count.
    """

    def test_create_universe_from_explicit_symbols(self, live_agent_chat):
        code = _test_universe("agent-symbols")
        response = live_agent_chat(
            f"Create a QuantRocket universe called '{code}' containing AAPL, MSFT, and GOOGL.",
        )
        assert not response.get("error"), f"Agent error: {response['error']}"

        universes = list_universes_fn()
        assert code in universes, (
            f"Agent said it created '{code}' but it was not found in QuantRocket.\n"
            f"Agent response: {response['message'][:300]}"
        )
        assert universes[code] == 3, (
            f"Expected 3 securities in '{code}', got {universes[code]}"
        )

    def test_create_universe_from_search_criteria(self, live_agent_chat):
        code = _test_universe("agent-reits")
        response = live_agent_chat(
            f"Search QuantRocket for up to 20 REIT securities and create a universe "
            f"called '{code}' from whatever results come back.",
        )
        assert not response.get("error"), f"Agent error: {response['error']}"

        universes = list_universes_fn()
        assert code in universes, (
            f"Agent said it created '{code}' but it was not found in QuantRocket.\n"
            f"Agent response: {response['message'][:300]}"
        )
        assert universes[code] > 0, (
            f"Universe '{code}' was created but contains 0 securities"
        )

    def test_create_universe_nasdaq_common_stocks(self, live_agent_chat):
        code = _test_universe("agent-nasdaq")
        response = live_agent_chat(
            f"Search for up to 20 NASDAQ-listed common stocks in QuantRocket "
            f"and create a universe called '{code}' from them.",
        )
        assert not response.get("error"), f"Agent error: {response['error']}"

        universes = list_universes_fn()
        assert code in universes, (
            f"Agent said it created '{code}' but it was not found in QuantRocket.\n"
            f"Agent response: {response['message'][:300]}"
        )
        assert universes[code] > 0, (
            f"Universe '{code}' was created but contains 0 securities"
        )
