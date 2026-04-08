import json
import sys
from pathlib import Path

# Ensure the project root is on sys.path so all packages are importable
# whether this file is run as a standalone script or as part of the FastAPI app.
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastmcp import FastMCP

from agent_backend.mcp_server.tools import (
    ZIPLINE_CATEGORIES,
    PIPELINE_CATEGORIES,
    get_functions_in_category,
    get_function_or_class_details,
    list_universes,
    search_securities,
    create_universe,
    delete_universe,
)


# Initialize FastMCP server
mcp = FastMCP("ZiplineStrategy")


@mcp.resource("ziplineApi://zipline_categories")
def get_zipline_categories() -> str:
    """Retrieve the available category slugs in the Zipline API.

    Use the get_functions_in_category tool with api_type="zipline" and a category slug to see functions in that category.
    """
    return json.dumps(ZIPLINE_CATEGORIES)


@mcp.resource("ziplineApi://pipeline_categories")
def get_pipeline_categories() -> str:
    """Retrieve the available category slugs in the Pipeline API.

    Use the get_functions_in_category tool with api_type="pipeline" and a category slug to see functions in that category.
    """
    return json.dumps(PIPELINE_CATEGORIES)


mcp.tool(get_functions_in_category)
mcp.tool(get_function_or_class_details)
mcp.tool(list_universes)
mcp.tool(search_securities)
mcp.tool(create_universe)
mcp.tool(delete_universe)


if __name__ == "__main__":
    mcp.run()
