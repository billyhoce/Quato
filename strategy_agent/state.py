"""
Agent State Schema

TypedDict definitions for LangGraph state management.
"""

from typing import TypedDict, Optional, Any


class StrategyAgentState(TypedDict):
    """State for the strategy agent graph."""
    
    # Input
    user_input: str  # Plaintext strategy description
    
    # Hypothesis/interpretation
    hypothesis: Optional[dict[str, Any]]  # Structured strategy interpretation
    
    # Code generation
    generated_code: str  # Generated Zipline Python code
    api_context: str  # Relevant API documentation gathered from MCP
    
    # Validation
    syntax_valid: bool  # Whether code passed syntax validation
    syntax_errors: Optional[str]  # Syntax error messages if validation failed
    
    # Human-in-the-loop
    human_feedback: str  # Feedback from human reviewer
    approved: bool  # Whether human approved the code
    
    # Backtesting
    backtest_results: Optional[dict[str, Any]]  # Results from backtest execution
    
    # Control flow
    iteration: int  # Current iteration count
    max_iterations: int  # Maximum allowed iterations
    
    # Messages/history
    messages: list[dict[str, str]]  # Conversation history for LLM context
