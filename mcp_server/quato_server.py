import json
import pprint
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

@mcp.resource("ziplineApi://overview_of_pipeline_functions_and_classes")
def get_pipeline_overview() -> dict:
    """Retrieve the list of functions and classes of the pipeline API."""
    functions_with_description = {}
    for function, data in pipeline_api_data.items():
        functions_with_description[function] = data.get("description", "No description available.")
    return functions_with_description

@mcp.resource("ziplineApi://overview_of_zipline_functions_and_classes")
def get_zipline_overview() -> dict:
    """Retrieve the list of functions and classes of the zipline API."""
    functions_with_description = {}
    for function, data in zipline_api_data.items():
        functions_with_description[function] = data.get("description", "No description available.")
    return functions_with_description

@mcp.tool
def get_function_or_class_details(function_class_names: list[str]) -> list[dict[str, Any]]:
    """Given a list of function or class names (Same format as the keys when retrieving overviews), retrieve their detailed information, including description and parameters."""
    details_list = [
        combined_api_data[name] 
        for name in function_class_names 
        if name in combined_api_data
    ]
    return details_list

if __name__ == "__main__":
    mcp.run()