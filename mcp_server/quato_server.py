import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Mock mode — set QUATO_MOCK=1 to return fake data without a QuantRocket server.
# Used by integration tests.
# ---------------------------------------------------------------------------
_MOCK = os.getenv("QUATO_MOCK") == "1"
import tempfile as _tempfile
_MOCK_LOG = Path(os.getenv("QUATO_MOCK_LOG", str(Path(_tempfile.gettempdir()) / "quato_mock_calls.jsonl")))

_MOCK_UNIVERSES: dict[str, int] = {
    "us-stocks": 8000,
    "us-etfs": 520,
    "tech-stocks": 420,
}

_MOCK_STK_DF = pd.DataFrame(
    {
        "Symbol": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"],
        "Name": [
            "Apple Inc", "Microsoft Corp", "Alphabet Inc",
            "Amazon.com Inc", "NVIDIA Corp", "Meta Platforms Inc", "Tesla Inc",
        ],
        "usstock_SecurityType2": ["Common Stock"] * 7,
        "Exchange": ["XNAS"] * 7,
        "SecType": ["STK"] * 7,
    },
    index=[
        "FIBBG000B9XRY4", "FIBBG000BPH459", "FIBBG000BVPV84",
        "FIBBG000BVKVH2", "FIBBG000BBJQV0", "FIBBG000MM2P62", "FIBBG000N9MNX3",
    ],
)

_MOCK_ETF_DF = pd.DataFrame(
    {
        "Symbol": ["SPY", "QQQ", "IWM"],
        "Name": [
            "SPDR S&P 500 ETF Trust", "Invesco QQQ Trust", "iShares Russell 2000 ETF",
        ],
        "usstock_SecurityType2": ["Mutual Fund"] * 3,
        "Exchange": ["ARCX", "XNAS", "ARCX"],
        "SecType": ["STK"] * 3,
    },
    index=["FIBBG000BDTBL9", "FIBBG000BSWKH7", "FIBBG000C2JQY0"],
)


def _mock_log(fn: str, **kwargs) -> None:
    with open(_MOCK_LOG, "a") as f:
        f.write(json.dumps({"fn": fn, **kwargs}) + "\n")

# Initialize FastMCP server
mcp = FastMCP("ZiplineStrategy")

# Load API documentation from JSON files
SCRIPT_DIR = Path(__file__).parent
PIPELINE_API_FILE = SCRIPT_DIR / "pipeline_api_parsed.json"
ZIPLINE_API_FILE = SCRIPT_DIR / "zipline_api_parsed.json"

# Load the JSON data
with open(PIPELINE_API_FILE, "r", encoding="utf-8") as f:
    pipeline_api_data = json.load(f)

with open(ZIPLINE_API_FILE, "r", encoding="utf-8") as f:
    zipline_api_data = json.load(f)

combined_api_data = {**pipeline_api_data, **zipline_api_data}


def _extract_categories(api_data: dict, api_type: str) -> list[str]:
    """Extract unique category slugs from API data keys.

    Keys follow the pattern docs/{api_type}/{category_slug}/{function}.
    """
    categories = set()
    prefix = f"docs/{api_type}/"
    for key in api_data:
        if key.startswith(prefix):
            # Extract category_slug from docs/{api_type}/{category_slug}/...
            rest = key[len(prefix):]
            slug = rest.split("/", 1)[0]
            categories.add(slug)
    return sorted(categories)


ZIPLINE_CATEGORIES = _extract_categories(zipline_api_data, "zipline")
PIPELINE_CATEGORIES = _extract_categories(pipeline_api_data, "pipeline")


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

@mcp.tool
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
    # Select the right API data
    api_data = pipeline_api_data if api_type == "pipeline" else zipline_api_data

    # Build the category prefix
    category_prefix = f"docs/{api_type}/{category_slug}/"

    # Filter functions by category and extract descriptions
    functions_in_category = {}
    for func_key, func_data in api_data.items():
        if func_key.startswith(category_prefix):
            functions_in_category[func_key] = func_data.get("description", "No description available.")

    return functions_in_category

@mcp.tool
def get_function_or_class_details(function_class_names: list[str]) -> list[dict[str, Any]]:
    """Given a list of function or class names
       (E.g ["docs/pipeline/built-in-factors/factors-dailyreturns", "docs/zipline/fee-models/set-borrow-fees-provider"]),
       retrieve their detailed information, including description and parameters."""
    details_list = [
        combined_api_data[name]
        for name in function_class_names
        if name in combined_api_data
    ]
    return details_list


@mcp.tool
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
    if _MOCK:
        _mock_log("list_universes")
        return dict(_MOCK_UNIVERSES)
    from quantrocket import master
    return master.list_universes()


@mcp.tool
def search_securities(
    exchanges: list[str] | None = None,
    sec_types: list[str] | None = None,
    usstock_security_type2: list[str] | None = None,
    vendors: list[str] | None = None,
    symbols: list[str] | None = None,
    universes: list[str] | None = None,
    exclude_delisted: bool = True,
    max_results: int = 200,
) -> list[dict[str, str | None]]:
    """Search the QuantRocket securities master for securities matching the given criteria.

    Use this to find the SIDs needed to build a universe, or to explore what
    securities are available before writing a strategy.

    IMPORTANT — two separate "type" fields exist and behave differently:

    sec_types vs usstock_security_type2
    ------------------------------------
    - `sec_types` is the generic QuantRocket security type. In this deployment
      ALL securities (common stocks, preferred shares, REITs, mutual funds, etc.)
      are stored as SecType="STK". Do NOT use sec_types to filter by asset class
      for US equities — it will not work as expected.

    - `usstock_security_type2` is the US-stock-specific subtype and is the
      correct way to filter by asset class. Known values in this deployment:
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
      NOTE: "ETF" does NOT exist as a usstock_SecurityType2 value — use
      "Mutual Fund" instead to find ETFs.

    For finer-grained filtering, usstock_SecurityType (the most granular field)
    can distinguish e.g. "Exchange Traded Fund" within "Mutual Fund", but this
    is not exposed as a filter parameter here. If you need that level of detail,
    ask the user to refine their request or check the securities list after
    searching with usstock_security_type2=["Mutual Fund"].

    The returned "security_type" key in each result reflects the
    usstock_SecurityType2 value so you can verify before creating a universe.

    Parameters
    ----------
    exchanges : list of str, optional
        Filter by exchange MIC codes (e.g. ["XNAS", "XNYS"] for NASDAQ / NYSE).
    sec_types : list of str, optional
        Generic security type filter. For US equities leave this as None and
        use usstock_security_type2 instead (see above).
    usstock_security_type2 : list of str, optional
        US-stock subtype filter. Use this to select asset classes reliably.
        e.g. ["Common Stock"], ["REIT"], ["Common Stock", "Depositary Receipt"].
    vendors : list of str, optional
        Filter by data vendor. Common values: "usstock", "ibkr", "sharadar".
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
        Each dict has keys: sid, symbol, name, security_type, exchange.
        security_type reflects the usstock_SecurityType2 value.
    """
    if _MOCK:
        _mock_log("search_securities", exchanges=exchanges, sec_types=sec_types,
                  usstock_security_type2=usstock_security_type2, symbols=symbols,
                  universes=universes)
        use_etf = (usstock_security_type2 and "Mutual Fund" in usstock_security_type2) or (
            sec_types and set(sec_types) == {"ETF"}
        )
        df = _MOCK_ETF_DF if use_etf else _MOCK_STK_DF
        if symbols:
            df = df[df["Symbol"].isin(symbols)]
        df = df.head(min(max_results, 500))
        return [
            {"sid": str(sid), "symbol": str(row.get("Symbol") or ""),
             "name": row.get("Name"), "security_type": row.get("usstock_SecurityType2"),
             "exchange": row.get("Exchange")}
            for sid, row in df.iterrows()
        ]
    from quantrocket import master
    # Build post-fetch filter for usstock_SecurityType2 (not a native API param)
    df = master.get_securities(
        exchanges=exchanges,
        sec_types=sec_types,
        vendors=vendors,
        symbols=symbols,
        universes=universes,
        exclude_delisted=exclude_delisted,
        fields=["Symbol", "Name", "usstock_SecurityType2", "Exchange", "SecType"],
    )
    if usstock_security_type2:
        df = df[df["usstock_SecurityType2"].isin(usstock_security_type2)]
    cap = min(max_results, 500)
    df = df.head(cap)
    result = []
    for sid, row in df.iterrows():
        result.append({
            "sid": str(sid),
            "symbol": str(row.get("Symbol") or ""),
            "name": row.get("Name") or None,
            "security_type": row.get("usstock_SecurityType2") or row.get("SecType") or None,
            "exchange": row.get("Exchange") or None,
        })
    return result


@mcp.tool
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
    if _MOCK:
        count = len(sids) if sids else 0
        _mock_log("create_universe", code=code, sids=sids, from_universes=from_universes)
        _MOCK_UNIVERSES[code] = count
        return {"code": code, "provided": count, "inserted": count, "total_after_insert": count}
    from quantrocket import master
    return master.create_universe(
        code=code,
        sids=sids,
        from_universes=from_universes,
        append=append,
        replace=replace,
    )


if __name__ == "__main__":
    mcp.run()