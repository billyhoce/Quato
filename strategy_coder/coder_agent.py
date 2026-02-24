import asyncio
import logging
import re
from datetime import datetime, date

from dotenv import load_dotenv
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient  
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent

from strategy_coder.constants import SYSTEM_PROMPT
from backtesting_orchestrator.orchestrator import BacktestingOrchestrator
from models.backtest_models import BacktestConfig

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


def extract_python_code(text: str) -> str | None:
    """Extract Python code from markdown code blocks or plain text."""
    # Try to find code in markdown code blocks
    code_block_pattern = r'```python\n(.*?)\n```'
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    if matches:
        return matches[0]
    
    # Try without language specifier
    code_block_pattern = r'```\n(.*?)\n```'
    matches = re.findall(code_block_pattern, text, re.DOTALL)
    if matches:
        return matches[0]
    
    # Check if the entire text looks like Python code
    if 'import' in text and 'def ' in text:
        return text
    
    return None


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

        # Initialize backtesting orchestrator
        logger.info("Initializing Backtesting Orchestrator...")
        orchestrator = BacktestingOrchestrator()

        turn = 0
        while True:
            try:
                user_query = input("\nYour input: ")
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

                response_content = agent_response['messages'][-1].content
                
                # Check if response contains Python code
                extracted_code = extract_python_code(response_content)
                
                if extracted_code:
                    print("\n" + "="*80)
                    print("STRATEGY CODE GENERATED")
                    print("="*80)
                    print(extracted_code)
                    print("="*80 + "\n")
                    
                    # Ask user if they want to backtest
                    backtest_choice = input("Would you like to backtest this strategy? (yes/no): ").strip().lower()
                    
                    if backtest_choice in ['yes', 'y']:
                        print("\n" + "="*80)
                        print("RUNNING BACKTEST")
                        print("="*80 + "\n")
                        
                        # Configure backtest
                        config = BacktestConfig(
                            start_date=date(2023, 1, 1),
                            end_date=date(2023, 12, 31),
                            capital_base=100000,
                            filepath_or_buffer=None  # Will be set by orchestrator
                        )
                        
                        # Run complete backtest workflow
                        result = orchestrator.backtest_strategy_from_code(
                            strategy_code=extracted_code,
                            config=config,
                            base_dir=base_dir
                        )
                        
                        # Display results
                        if result["success"]:
                            print(f"\n✓ Strategy saved to: {result['strategy_path']}")
                            print(f"✓ Backtest completed successfully!")
                            print(f"✓ Results saved to: {result['results_file']}")
                            print(f"✓ Tearsheet generated: {result['tearsheet_file']}\n")
                        else:
                            print(f"\n✗ {result['error_message']}\n")
                            print("You can review the strategy code and try again.\n")
                else:
                    # No code detected, just print the response
                    print(f"\nAgent Response: {response_content}\n")

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