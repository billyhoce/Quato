import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

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
    make_backtest_tools,
)
from backtesting.queue.backtest_queue import BacktestQueue
from backtesting.storage.object_store import ObjectStoreService


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Initialize backtest services and register backtest tools at startup."""
    queue = BacktestQueue()      # reads REDIS_URL from env (forwarded by agent_service.py)
    store = ObjectStoreService() # reads OBJECT_STORE_* from env; only constructs boto3 client
    await queue.connect()

    submit_backtest, get_backtest_status, get_backtest_results = make_backtest_tools(queue, store)
    server.tool(submit_backtest)
    server.tool(get_backtest_status)
    server.tool(get_backtest_results)

    try:
        yield
    finally:
        await queue.close()


# Initialize FastMCP server
mcp = FastMCP("ZiplineStrategy", lifespan=lifespan)


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


if __name__ == "__main__":
    mcp.run()
