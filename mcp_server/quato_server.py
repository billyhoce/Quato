import json
import pandas as pd
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from quantrocket import master

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
    from quantrocket import master
    return master.list_universes()


@mcp.tool
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