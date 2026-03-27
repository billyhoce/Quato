"""
Integration test: agent universe creation behavior.

Runs the full LangGraph agent (real LLM, real MCP server subprocess) with a mock
QuantRocket module injected via PYTHONPATH so no live QuantRocket server is needed.

Prerequisites:
  - ANTHROPIC_API_KEY set in environment (or .env at project root)
  - Redis running on localhost:6379 (or REDIS_URL set)
    → OR: pass --no-redis to use in-memory checkpointer

Usage:
  python tests/test_universe_agent.py
  python tests/test_universe_agent.py --no-redis
"""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TESTS_DIR = Path(__file__).parent
PROJECT_ROOT = TESTS_DIR.parent
MOCK_QR_DIR = TESTS_DIR / "mock_qr"

# Add project root to path
sys.path.insert(0, str(PROJECT_ROOT))

# Tell the MCP subprocess to use built-in mock mode (no QuantRocket server needed)
os.environ["QUATO_MOCK"] = "1"

# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------
SCENARIOS = [
    {
        "name": "List existing universes",
        "message": "What universes do I have in QuantRocket?",
        "expect_tool_calls": ["list_universes"],
        "must_not_call": ["create_universe"],
    },
    {
        "name": "Create a tech stocks universe",
        "message": (
            "Create a universe called 'my-tech' containing AAPL, MSFT, GOOGL, "
            "AMZN, NVDA, META, and TSLA."
        ),
        "expect_tool_calls": ["create_universe"],
        "must_not_call": [],
    },
    {
        "name": "Create universe from search (by exchange + type)",
        "message": (
            "I want to trade only NASDAQ-listed common stocks. "
            "Create a universe called 'nasdaq-common' for me."
        ),
        "expect_tool_calls": ["search_securities", "create_universe"],
        "must_not_call": [],
    },
    {
        "name": "Create ETF universe",
        "message": (
            "Find all ETFs available in QuantRocket and create a universe "
            "called 'all-etfs' from them."
        ),
        "expect_tool_calls": ["search_securities", "create_universe"],
        "must_not_call": [],
    },
    {
        "name": "Strategy using existing universe",
        "message": (
            "Write a simple momentum strategy that only trades stocks in "
            "the 'tech-stocks' universe."
        ),
        "expect_tool_calls": ["list_universes"],
        "must_not_call": [],
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_tool_calls(messages: list) -> list[str]:
    """Return a flat list of tool names called by the agent."""
    names = []
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            for tc in tool_calls:
                name = tc["name"] if isinstance(tc, dict) else tc.name
                names.append(name)
    return names


def read_mock_log(log_path: Path) -> list[dict]:
    """Read JSON-lines call log written by the mock QuantRocket module."""
    if not log_path.exists():
        return []
    calls = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                calls.append(json.loads(line))
    return calls


def clear_mock_log(log_path: Path) -> None:
    if log_path.exists():
        log_path.unlink()


PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def check_scenario(scenario: dict, tool_calls: list[str], mock_calls: list[dict]) -> bool:
    ok = True
    missing = [t for t in scenario["expect_tool_calls"] if t not in tool_calls]
    unexpected = [t for t in scenario["must_not_call"] if t in tool_calls]

    if missing:
        print(f"  {FAIL} Missing expected tool calls: {missing}")
        ok = False
    else:
        print(f"  {PASS} Expected tool calls present: {scenario['expect_tool_calls']}")

    if unexpected:
        print(f"  {FAIL} Unexpected tool calls found: {unexpected}")
        ok = False

    # Show which QuantRocket functions were actually called in the subprocess
    if mock_calls:
        fn_names = [c["fn"] for c in mock_calls]
        print(f"  {PASS} QuantRocket calls made: {fn_names}")
    else:
        print(f"  {WARN} No QuantRocket mock calls logged (tool may not have been invoked)")

    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_tests(use_redis: bool = True) -> None:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=True)

    # Set mock log path (cross-platform temp dir)
    import tempfile
    log_file = Path(tempfile.gettempdir()) / "quato_mock_calls.jsonl"
    os.environ["QUATO_MOCK_LOG"] = str(log_file)

    # Checkpointer
    if use_redis:
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        checkpointer_ctx = AsyncRedisSaver.from_conn_string(redis_url)
    else:
        from langgraph.checkpoint.memory import MemorySaver
        import contextlib

        @contextlib.asynccontextmanager
        async def _mem_ctx():
            yield MemorySaver()

        checkpointer_ctx = _mem_ctx()

    from services.agent_service import AgentService
    from services.strategy_manager import StrategyManager

    strategy_manager = StrategyManager()
    agent_service = AgentService(strategy_manager)

    print("=" * 60)
    print("Universe Agent Integration Tests")
    print("=" * 60)

    async with checkpointer_ctx as checkpointer:
        await strategy_manager.connect()
        try:
            print("\nInitializing agent (starting MCP server)...")
            await agent_service.initialize(checkpointer)
            print("Agent ready.\n")

            results = []

            for i, scenario in enumerate(SCENARIOS, 1):
                session_id = f"test-universe-{uuid.uuid4().hex[:8]}"
                clear_mock_log(log_file)

                print(f"[{i}/{len(SCENARIOS)}] {scenario['name']}")
                print(f"  User: {scenario['message'][:80]}...")

                try:
                    response = await agent_service.chat(session_id, scenario["message"])

                    if response.get("error"):
                        print(f"  {FAIL} Agent error: {response['error']}")
                        results.append(False)
                        continue

                    # Get tool calls from LangGraph message history
                    agent_state = await agent_service.agent.aget_state(
                        {"configurable": {"thread_id": session_id}}
                    )
                    tool_calls = extract_tool_calls(agent_state.values.get("messages", []))
                    mock_calls = read_mock_log(log_file)

                    print(f"  Agent: {response['message'][:120]}...")
                    print(f"  All tool calls: {tool_calls}")

                    ok = check_scenario(scenario, tool_calls, mock_calls)
                    results.append(ok)

                except Exception as e:
                    print(f"  {FAIL} Exception: {e}")
                    results.append(False)

                print()

            # Summary
            passed = sum(results)
            total = len(results)
            print("=" * 60)
            if passed == total:
                print(f"{PASS} All {total} scenarios passed")
            else:
                print(f"{FAIL} {passed}/{total} scenarios passed")
            print("=" * 60)

        finally:
            await strategy_manager.close()


if __name__ == "__main__":
    use_redis = "--no-redis" not in sys.argv
    asyncio.run(run_tests(use_redis=use_redis))
