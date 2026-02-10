import asyncio
import logging

from dotenv import load_dotenv
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient  
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent

from constants import SYSTEM_PROMPT

# Configure logging
log_filename = f"coder_agent.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def main():
    try:
        load_dotenv(override=True)

        base_dir = Path(__file__).parent.parent
        mcp_server_path = base_dir / "mcp_server" / "quato_server.py"
        logger.info(f"Starting MCP client for server at: {mcp_server_path}")

        client = MultiServerMCPClient(  
            {
                "ZiplineStrategy": {
                    "transport": "stdio",
                    "command": "python",
                    "args": [str(mcp_server_path)],
                }
            }
        )

        logger.info("Fetching resources from MCP server...")
        resources = await client.get_resources()
        extracted_resources = {}
        for blob in resources:
            logger.info(f"Found Resource with URI: {blob.metadata['uri']}, MIME Type: {blob.mimetype}, Size: {len(blob.data)} bytes")
            extracted_resources[blob.metadata['uri']] = blob.data

        logger.info("Creating agent with MCP tools...")
        tools = await client.get_tools()

        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=1.0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )

        agent = create_agent(
            model=model,
            tools=tools,
            checkpointer=InMemorySaver()
        )

        turn = 0
        while True:
            try:
                user_query = input("Your input: ")
                if user_query.lower() == 'exit':
                    logger.info("User exited the application")
                    break
                
                if turn == 0:
                    prompt = SYSTEM_PROMPT + "Here are the different zipline APIs, use the tool to find out more\n" + str(extracted_resources) + "User Query: \n" + user_query
                else:
                    prompt = user_query

                logger.info(f"Processing user query (turn {turn})")
                agent_response = await agent.ainvoke(
                    {"messages": [{"role": "user", "content": prompt}]},
                    {"configurable": {"thread_id": "1"}}        
                )

                logger.info(f"Agent response: {agent_response}")

                # Print agent response to stdio for user to respond to
                print(f"Agent Response: {agent_response['messages'][-1].content}")

                turn += 1
            except KeyboardInterrupt:
                logger.info("Application interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error processing query: {str(e)}", exc_info=True)
                logger.info("Continuing to next iteration...")
    except Exception as e:
        logger.error(f"Fatal error in main(): {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())