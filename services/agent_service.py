"""Agent Service for handling LLM interactions and strategy generation."""
import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

from services.constants import SYSTEM_PROMPT
from services.strategy_manager import StrategyManager

logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing agent interactions and strategy generation.
    
    Handles LLM-based conversations, code extraction, and strategy updates
    across multiple sessions.
    """
    
    def __init__(self, strategy_manager: StrategyManager):
        """Initialize the agent service.
        
        Args:
            strategy_manager: StrategyManager instance for storing strategies
        """
        self.strategy_manager = strategy_manager
        self.agent = None
        self.resources = {}
        self._initialized = False
        logger.info("AgentService created")
    
    async def initialize(self, checkpointer):
        """Initialize the agent with MCP tools and resources.

        Args:
            checkpointer: LangGraph checkpoint backend (e.g. AsyncRedisSaver).
                          Must outlive this service — the caller owns its lifecycle.
        """
        if self._initialized:
            logger.info("AgentService already initialized")
            return
        
        load_dotenv(override=True)
        
        base_dir = Path(__file__).parent.parent
        mcp_server_path = base_dir / "mcp_server" / "quato_server.py"
        logger.info(f"Starting MCP client for server at: {mcp_server_path}")
        
        client = MultiServerMCPClient({
            "ZiplineStrategy": {
                "transport": "stdio",
                "command": "python",
                "args": [str(mcp_server_path)],
                "env": dict(os.environ),
            }
        })
        
        logger.info("Fetching resources from MCP server...")
        resources = await client.get_resources()
        for blob in resources:
            logger.info(f"Found Resource with URI: {blob.metadata['uri']}")
            self.resources[str(blob.metadata['uri'])] = json.loads(blob.data)
        
        logger.info("Creating agent with MCP tools...")
        tools = await client.get_tools()
        
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=1.0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
        )
        
        self.agent = create_agent(
            model="claude-sonnet-4-6",
            tools=tools,
            checkpointer=checkpointer
        )
        
        self._initialized = True
        logger.info("AgentService initialized successfully")
    
    def _extract_text(self, content) -> str:
        """Normalise agent response content to a plain string.

        LangGraph message content can be a plain string (simple text response)
        or a list of content blocks (multimodal / tool-use responses). Both
        paths now feed into the same extraction so downstream parsing is
        consistent.
        """
        if isinstance(content, list):
            return "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        return str(content)

    def _parse_agent_response(self, content) -> tuple[str, Optional[str]]:
        """Parse agent response to extract explanation and code separately.
        
        Args:
            content: Agent response content (string or list)
            
        Returns:
            Tuple of (explanation, code)
            - explanation: Text explanation without code blocks
            - code: Just the Python code, or None if no code
        """
        # Extract code from markdown blocks
        code_block_pattern = r'```python\n(.*?)\n```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        if matches:
            # Remove code block from explanation
            explanation = re.sub(r'```python\n.*?\n```', '', content, flags=re.DOTALL).strip()
            return explanation, matches[0]
        
        # Try without language specifier
        code_block_pattern = r'```\n(.*?)\n```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        if matches:
            # Remove code block from explanation
            explanation = re.sub(r'```\n.*?\n```', '', content, flags=re.DOTALL).strip()
            return explanation, matches[0]
        
        # Check if entire text is code (no explanation provided)
        if 'import' in content and 'def ' in content:
            return "Here's the strategy code:", content
        
        # No code found
        return content, None
    
    async def chat(self, session_id: str, message: str) -> dict:
        """Process a chat message and return response with strategy updates.
        
        Args:
            session_id: Unique identifier for the session
            message: User's message to the agent
            
        Returns:
            Dictionary with:
                - message: Agent's response text
                - strategy_updated: Whether strategy was updated
                - strategy_code: Updated strategy code (if updated)
                - error: Error message (if any)
        """
        if not self._initialized:
            raise RuntimeError("AgentService not initialized. Call initialize() first.")
        
        try:
            # Atomically get the current turn and increment the counter in Redis.
            # Returns 0 on the first message for this session, 1 on the second, etc.
            turn = await self.strategy_manager.get_and_increment_turn(session_id)

            # Build prompt
            if turn == 0:
                # On first turn, include system prompt and available categories
                categories_info = (
                    "\n\nAvailable API category slugs (use with get_functions_in_category(api_type, category_slug)):\n\n"
                    "Zipline (api_type=\"zipline\"):\n" +
                    "\n".join(f"  - {slug}"
                             for slug in self.resources.get('ziplineapi://zipline_categories', [])) +
                    "\n\nPipeline (api_type=\"pipeline\"):\n" +
                    "\n".join(f"  - {slug}"
                             for slug in self.resources.get('ziplineapi://pipeline_categories', [])) +
                    "\n"
                )
                prompt = SYSTEM_PROMPT + categories_info + "User Query: \n" + message
            else:
                prompt = message
            
            logger.info(f"Processing message for session {session_id}, turn {turn}")
            
            # Get agent response
            agent_response = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                {"configurable": {"thread_id": session_id}}
            )
            
            response_content = self._extract_text(agent_response['messages'][-1].content)

            # Retry once if response is empty
            if not response_content.strip():
                logger.warning(f"Empty response from agent for session {session_id}, retrying...")
                agent_response = await self.agent.ainvoke(
                    {"messages": [{"role": "user", "content": prompt}]},
                    {"configurable": {"thread_id": session_id}}
                )
                response_content = self._extract_text(agent_response['messages'][-1].content)
            
            # Parse response to separate explanation and code
            explanation, extracted_code = self._parse_agent_response(response_content)
            
            strategy_updated = False
            if extracted_code:
                await self.strategy_manager.set_strategy(session_id, extracted_code)
                strategy_updated = True
                logger.info(f"Strategy updated for session {session_id}")

            return {
                "message": explanation,  # Return just the explanation text
                "strategy_updated": strategy_updated,
                "strategy_code": extracted_code if strategy_updated else None,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error processing message for session {session_id}: {str(e)}", exc_info=True)
            return {
                "message": "",
                "strategy_updated": False,
                "strategy_code": None,
                "error": str(e)
            }
    
