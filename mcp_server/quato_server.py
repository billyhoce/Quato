import sys
from pathlib import Path

# Ensure the project root is on sys.path so `mcp_server.tools` is importable
# whether this file is run as a standalone script or as part of the FastAPI app.
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastmcp import FastMCP

from mcp_server.tools import (
    ZIPLINE_CATEGORIES,
    PIPELINE_CATEGORIES,
    get_functions_in_category,
    get_function_or_class_details,
    list_universes,
    search_securities,
    create_universe,
)

# Initialize FastMCP server
mcp = FastMCP("ZiplineStrategy")


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


mcp.tool(get_functions_in_category)
mcp.tool(get_function_or_class_details)
mcp.tool(list_universes)
mcp.tool(search_securities)
mcp.tool(create_universe)


if __name__ == "__main__":
    mcp.run()
