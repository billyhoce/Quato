import asyncio
from anyio import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

current_directory = Path(__file__).parent

transport = StdioTransport(
    command="python",
    args=[str(current_directory / "quato_server.py")]
)
client = Client(transport)

async def main():
    async with client:
        # Basic server interaction
        await client.ping()
        
        # List available operations
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        print("Available Tools:", tools)
        print("Available Resources:", resources)
        print("Available Prompts:", prompts)
        
        # Execute operations
        result = await client.call_tool(
            "get_function_or_class_details", 
            {"function_class_names": ["docs/pipeline/periodic-factors-and-filters/periodic-periodichigh"]}
        )
        print(result)

asyncio.run(main())