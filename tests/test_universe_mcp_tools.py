"""
Unit tests for the universe-related MCP tools in mcp_server/quato_server.py.

QuantRocket is mocked via sys.modules injection so no server is needed.
Run with: pytest tests/test_universe_mcp_tools.py -v
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, call

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Inject mock quantrocket BEFORE importing quato_server so the local imports
# inside the tool functions resolve to the mock.
# ---------------------------------------------------------------------------
_mock_master = MagicMock()

_FAKE_UNIVERSES = {"us-stocks": 8000, "tech-stocks": 420, "nyse-etfs": 52}

_FAKE_DF = pd.DataFrame(
    {
        "Symbol": ["AAPL", "MSFT", "GOOGL", "AMZN"],
        "Name": ["Apple Inc", "Microsoft Corp", "Alphabet Inc", "Amazon.com Inc"],
        "usstock_SecurityType2": ["Common Stock"] * 4,
        "Exchange": ["XNAS"] * 4,
        "SecType": ["STK"] * 4,
    },
    index=["FIBBG000B9XRY4", "FIBBG000BPH459", "FIBBG000BVPV84", "FIBBG000BVKVH2"],
)

_mock_master.list_universes.return_value = dict(_FAKE_UNIVERSES)
_mock_master.get_securities.return_value = _FAKE_DF.copy()
_mock_master.create_universe.return_value = {
    "status": "successfully created universe 'test-universe' with 4 securities"
}

_mock_qr_pkg = types.ModuleType("quantrocket")
_mock_qr_pkg.master = _mock_master
sys.modules.setdefault("quantrocket", _mock_qr_pkg)
sys.modules.setdefault("quantrocket.master", _mock_master)

# Add project root so quato_server is importable
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agent_backend.mcp_server.quato_server import (  # noqa: E402 — must come after sys.modules patch
    create_universe as _create_universe_tool,
    list_universes as _list_universes_tool,
    search_securities as _search_securities_tool,
)

# FastMCP wraps functions in FunctionTool objects; .fn is the raw callable.
list_universes = _list_universes_tool.fn
search_securities = _search_securities_tool.fn
create_universe = _create_universe_tool.fn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mock call counts before every test."""
    _mock_master.reset_mock()
    _mock_master.list_universes.return_value = dict(_FAKE_UNIVERSES)
    _mock_master.get_securities.return_value = _FAKE_DF.copy()
    _mock_master.create_universe.return_value = {
        "status": "successfully created universe 'test-universe' with 4 securities"
    }
    yield


# ---------------------------------------------------------------------------
# list_universes
# ---------------------------------------------------------------------------

class TestListUniverses:
    def test_returns_dict(self):
        result = list_universes()
        assert isinstance(result, dict)

    def test_contains_expected_keys(self):
        result = list_universes()
        assert "us-stocks" in result
        assert result["us-stocks"] == 8000

    def test_delegates_to_quantrocket(self):
        list_universes()
        _mock_master.list_universes.assert_called_once_with()

    def test_returns_all_universes(self):
        result = list_universes()
        assert len(result) == len(_FAKE_UNIVERSES)


# ---------------------------------------------------------------------------
# search_securities
# ---------------------------------------------------------------------------

class TestSearchSecurities:
    def test_returns_list_of_dicts(self):
        result = search_securities()
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    def test_expected_keys_present(self):
        result = search_securities()
        for item in result:
            assert "sid" in item
            assert "symbol" in item
            assert "name" in item
            assert "security_type" in item
            assert "exchange" in item

    def test_passes_exchanges_filter(self):
        search_securities(exchanges=["XNYS"])
        _, kwargs = _mock_master.get_securities.call_args
        assert kwargs["exchanges"] == ["XNYS"]

    def test_passes_sec_types_filter(self):
        search_securities(sec_types=["ETF"])
        _, kwargs = _mock_master.get_securities.call_args
        assert kwargs["sec_types"] == ["ETF"]

    def test_passes_symbols_filter(self):
        search_securities(symbols=["AAPL", "MSFT"])
        _, kwargs = _mock_master.get_securities.call_args
        assert kwargs["symbols"] == ["AAPL", "MSFT"]

    def test_exclude_delisted_forwarded(self):
        search_securities(exclude_delisted=False)
        _, kwargs = _mock_master.get_securities.call_args
        assert kwargs["exclude_delisted"] is False

    def test_max_results_caps_output(self):
        result = search_securities(max_results=2)
        assert len(result) <= 2

    def test_max_results_hard_cap_at_500(self):
        # Even if caller asks for more, should be capped at 500
        big_df = pd.DataFrame(
            {"Symbol": [f"X{i}" for i in range(600)],
             "longName": [None] * 600,
             "usstock_SecurityType2": [None] * 600,
             "Exchange": [None] * 600,
             "SecType": ["STK"] * 600},
            index=[f"FI{i:06d}" for i in range(600)],
        )
        _mock_master.get_securities.return_value = big_df
        result = search_securities(max_results=600)
        assert len(result) <= 500

    def test_sid_is_string(self):
        result = search_securities()
        for item in result:
            assert isinstance(item["sid"], str)


# ---------------------------------------------------------------------------
# create_universe
# ---------------------------------------------------------------------------

class TestCreateUniverse:
    def test_returns_dict(self):
        result = create_universe("test-uni", sids=["FI123", "FI456"])
        assert isinstance(result, dict)

    def test_passes_code_to_quantrocket(self):
        create_universe("my-universe", sids=["FI123"])
        _, kwargs = _mock_master.create_universe.call_args
        assert kwargs["code"] == "my-universe"

    def test_passes_sids_to_quantrocket(self):
        sids = ["FIBBG000B9XRY4", "FIBBG000BPH459"]
        create_universe("test-uni", sids=sids)
        _, kwargs = _mock_master.create_universe.call_args
        assert kwargs["sids"] == sids

    def test_passes_from_universes_to_quantrocket(self):
        create_universe("sub-uni", from_universes=["us-stocks"])
        _, kwargs = _mock_master.create_universe.call_args
        assert kwargs["from_universes"] == ["us-stocks"]

    def test_append_flag_forwarded(self):
        create_universe("my-uni", sids=["FI1"], append=True)
        _, kwargs = _mock_master.create_universe.call_args
        assert kwargs["append"] is True

    def test_replace_flag_forwarded(self):
        create_universe("my-uni", sids=["FI1"], replace=True)
        _, kwargs = _mock_master.create_universe.call_args
        assert kwargs["replace"] is True

    def test_defaults_are_false(self):
        create_universe("my-uni", sids=["FI1"])
        _, kwargs = _mock_master.create_universe.call_args
        assert kwargs["append"] is False
        assert kwargs["replace"] is False
