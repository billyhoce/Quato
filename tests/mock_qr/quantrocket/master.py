"""
Mock implementation of quantrocket.master for agent integration tests.
Returned data is intentionally small so responses are fast and deterministic.
"""
import json
import os
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Call log — written to a JSON-lines file so the test process can read it
# ---------------------------------------------------------------------------
_LOG_FILE = Path(os.environ.get("QUATO_MOCK_LOG", "/tmp/quato_mock_calls.jsonl"))


def _log(fn: str, kwargs: dict) -> None:
    with open(_LOG_FILE, "a") as f:
        f.write(json.dumps({"fn": fn, **kwargs}) + "\n")


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
_UNIVERSES: dict[str, int] = {
    "us-stocks": 8000,
    "us-etfs": 520,
    "tech-stocks": 420,
}

_SECURITIES = pd.DataFrame(
    {
        "Symbol": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
        "Name": [
            "Apple Inc",
            "Microsoft Corp",
            "Alphabet Inc",
            "Amazon.com Inc",
            "NVIDIA Corp",
            "Meta Platforms Inc",
            "Tesla Inc",
        ],
        "usstock_SecurityType2": ["Common Stock"] * 7,
        "Exchange": ["XNAS"] * 7,
        "SecType": ["STK"] * 7,
    },
    index=[
        "FIBBG000B9XRY4",
        "FIBBG000BPH459",
        "FIBBG000BVPV84",
        "FIBBG000BVKVH2",
        "FIBBG000BBJQV0",
        "FIBBG000MM2P62",
        "FIBBG000N9MNX3",
    ],
)

_ETF_SECURITIES = pd.DataFrame(
    {
        "Symbol": ["SPY", "QQQ", "IWM"],
        "Name": [
            "SPDR S&P 500 ETF Trust",
            "Invesco QQQ Trust",
            "iShares Russell 2000 ETF",
        ],
        "usstock_SecurityType2": ["Mutual Fund"] * 3,
        "Exchange": ["ARCX", "XNAS", "ARCX"],
        "SecType": ["STK"] * 3,
    },
    index=["FIBBG000BDTBL9", "FIBBG000BSWKH7", "FIBBG000C2JQY0"],
)


# ---------------------------------------------------------------------------
# Public API (mirrors quantrocket.master signatures)
# ---------------------------------------------------------------------------

def list_universes() -> dict[str, int]:
    _log("list_universes", {})
    return dict(_UNIVERSES)


def get_securities(
    exchanges=None,
    sec_types=None,
    vendors=None,
    symbols=None,
    universes=None,
    exclude_delisted=True,
    exclude_expired=True,
    fields=None,
    **kwargs,
) -> pd.DataFrame:
    _log(
        "get_securities",
        {
            "exchanges": exchanges,
            "sec_types": sec_types,
            "vendors": vendors,
            "symbols": symbols,
            "universes": universes,
        },
    )

    # Return ETFs if sec_types is ETF-only, otherwise return stocks
    if sec_types and set(sec_types) == {"ETF"}:
        df = _ETF_SECURITIES.copy()
    else:
        df = _SECURITIES.copy()

    if symbols:
        df = df[df["Symbol"].isin(symbols)]

    return df


def create_universe(
    code: str,
    infilepath_or_buffer=None,
    sids=None,
    from_universes=None,
    exclude_delisted: bool = False,
    append: bool = False,
    replace: bool = False,
) -> dict[str, str]:
    count = len(sids) if sids else 0
    _log("create_universe", {"code": code, "sids": sids, "from_universes": from_universes})
    _UNIVERSES[code] = count
    return {"status": f"successfully created universe '{code}' with {count} securities"}
