import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

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

if __name__ == "__main__":
    mcp.run()