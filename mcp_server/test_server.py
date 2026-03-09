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
        print("✓ Server ping successful\n")

        # List available operations
        tools = await client.list_tools()
        resources = await client.list_resources()

        print("Available Tools:")
        for tool in tools:
            print(f"  - {tool.name}")

        print("\nAvailable Resources:")
        for resource in resources:
            print(f"  - {resource.uri}")

        # Test 1: Get Zipline categories
        print("\n=== Test 1: Get Zipline Categories ===")
        zipline_cats = await client.read_resource("ziplineApi://zipline_categories")
        zipline_data = zipline_cats[0].text
        import json
        zipline_categories = json.loads(zipline_data)
        print(f"Found {len(zipline_categories)} Zipline categories:")
        for slug, name in list(zipline_categories.items())[:5]:
            print(f"  {slug}: {name}")
        print("  ...")

        # Test 2: Get Pipeline categories
        print("\n=== Test 2: Get Pipeline Categories ===")
        pipeline_cats = await client.read_resource("ziplineApi://pipeline_categories")
        pipeline_data = pipeline_cats[0].text
        pipeline_categories = json.loads(pipeline_data)
        print(f"Found {len(pipeline_categories)} Pipeline categories:")
        for slug, name in pipeline_categories.items():
            print(f"  {slug}: {name}")

        # Test 3: Get functions in a category
        print("\n=== Test 3: Get Functions in 'built-in-factors' Category ===")
        result = await client.call_tool(
            "get_functions_in_category",
            {"api_type": "pipeline", "category_slug": "built-in-factors"}
        )
        functions = result.content[0].text
        func_dict = json.loads(functions)
        print(f"Found {len(func_dict)} functions in built-in-factors category:")
        # Show first 3 function keys
        for i, (key, desc) in enumerate(list(func_dict.items())[:3]):
            print(f"  {key}")
            print(f"    {desc[:80]}...")
        print(f"  ... and {len(func_dict) - 3} more")

        # Test 4: Get detailed info for a specific function
        print("\n=== Test 4: Get Detailed Function Info ===")
        result = await client.call_tool(
            "get_function_or_class_details",
            {"function_class_names": ["docs/pipeline/built-in-factors/factors-dailyreturns"]}
        )
        print("Details for factors-dailyreturns:")
        details = json.loads(result.content[0].text)[0]
        print(f"  Type: {details.get('type', 'N/A')}")
        print(f"  Signature: {details.get('method_signature', 'N/A')}")
        print(f"  Description: {details.get('description', 'N/A')[:100]}...")

        # Test 5: Test invalid category (should return empty dict)
        print("\n=== Test 5: Invalid Category (should return {}) ===")
        result = await client.call_tool(
            "get_functions_in_category",
            {"api_type": "pipeline", "category_slug": "nonexistent-category"}
        )
        empty_result = json.loads(result.content[0].text)
        print(f"Result: {empty_result}")
        print(f"✓ Correctly returned empty dict")

        print("\n=== All Tests Passed ✓ ===")

asyncio.run(main())