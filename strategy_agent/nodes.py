"""
LangGraph Node Implementations

Node functions for the strategy agent graph.
"""

from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
import os

from strategy_agent.state import StrategyAgentState
from strategy_agent.tools import ALL_TOOLS
from strategy_coder.coder import StrategyCoder
from strategy_coder.constants import SYSTEM_PROMPT


def parse_strategy_node(state: StrategyAgentState) -> dict[str, Any]:
    """
    Parse user input and create a structured hypothesis.
    
    Args:
        state: Current agent state
        
    Returns:
        State updates with hypothesis
    """
    user_input = state["user_input"]
    
    # Create a structured interpretation of the strategy
    hypothesis = {
        "id": f"strategy_{state['iteration']}",
        "description": user_input,
        "market": "stocks",  # Default, could be extracted from input
        "timeframe": "daily",  # Default, could be extracted from input
    }
    
    return {
        "hypothesis": hypothesis,
        "messages": state.get("messages", []) + [
            {"role": "user", "content": user_input}
        ]
    }


def research_api_node(state: StrategyAgentState) -> dict[str, Any]:
    """
    Query MCP server for relevant API documentation.
    
    Args:
        state: Current agent state
        
    Returns:
        State updates with API context
    """
    from strategy_agent.tools import query_pipeline_api, query_zipline_api
    
    # Get API overviews
    pipeline_overview = query_pipeline_api.invoke({})
    zipline_overview = query_zipline_api.invoke({})
    
    # Format API context for the LLM
    api_context = "# Zipline API Overview\n\n"
    for name, desc in list(zipline_overview.items())[:20]:  # Limit to prevent token overflow
        api_context += f"- {name}: {desc}\n"
    
    api_context += "\n# Pipeline API Overview\n\n"
    for name, desc in list(pipeline_overview.items())[:20]:
        api_context += f"- {name}: {desc}\n"
    
    return {"api_context": api_context}


def generate_code_node(state: StrategyAgentState) -> dict[str, Any]:
    """
    Generate Zipline strategy code using LLM with API context.
    
    Args:
        state: Current agent state
        
    Returns:
        State updates with generated code
    """
    # Get API key from environment if not in state
    api_key = os.getenv("OPENAI_API_KEY")
    
    # Initialize LLM (model should come from config, but we'll use a default for now)
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.1,
        api_key=api_key
    )
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    
    # Prepare messages
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"\n\nAvailable API Documentation:\n{state['api_context']}"),
    ]
    
    # Add conversation history
    for msg in state.get("messages", []):
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    
    # Add human feedback if present
    if state.get("human_feedback"):
        messages.append(HumanMessage(
            content=f"Please revise the code based on this feedback:\n{state['human_feedback']}"
        ))
    
    # Add the current request
    hypothesis = state["hypothesis"]
    prompt = f"Generate a complete Zipline strategy file for the following trading strategy:\n\n{hypothesis['description']}"
    
    if not state.get("human_feedback"):  # Only add on first generation
        messages.append(HumanMessage(content=prompt))
    
    # Generate code
    response = llm_with_tools.invoke(messages)
    
    # Extract code from response
    generated_code = response.content
    
    # Clean up markdown code blocks if present
    if "```python" in generated_code:
        generated_code = generated_code.split("```python")[1].split("```")[0].strip()
    elif "```" in generated_code:
        generated_code = generated_code.split("```")[1].split("```")[0].strip()
    
    return {
        "generated_code": generated_code,
        "messages": state.get("messages", []) + [
            {"role": "assistant", "content": generated_code}
        ]
    }


def validate_syntax_node(state: StrategyAgentState) -> dict[str, Any]:
    """
    Validate the syntax of generated code.
    
    Args:
        state: Current agent state
        
    Returns:
        State updates with validation results
    """
    coder = StrategyCoder()
    is_valid, error_msg = coder.validate_code(state["generated_code"])
    
    return {
        "syntax_valid": is_valid,
        "syntax_errors": error_msg
    }


def human_review_node(state: StrategyAgentState) -> dict[str, Any]:
    """
    Human-in-the-loop review node.
    
    This node is where execution pauses for human approval.
    The graph will interrupt before this node, allowing the human
    to review the generated code and provide feedback.
    
    Args:
        state: Current agent state
        
    Returns:
        State updates (no changes, just passes through)
    """
    # This node doesn't do anything - it's just a marker for the interrupt point
    # The human will update the state with approval/feedback before resuming
    return {}


def backtest_node(state: StrategyAgentState) -> dict[str, Any]:
    """
    Execute the backtest using the orchestrator.
    
    Args:
        state: Current agent state
        
    Returns:
        State updates with backtest results
    """
    # This would integrate with the BacktestingOrchestrator
    # For now, return a placeholder
    
    # from backtesting_orchestrator.orchestrator import BacktestingOrchestrator
    # orchestrator = BacktestingOrchestrator()
    # results = orchestrator.run_backtest(state["generated_code"])
    
    backtest_results = {
        "status": "pending",
        "message": "Backtest execution not yet implemented"
    }
    
    return {"backtest_results": backtest_results}


def apply_feedback_node(state: StrategyAgentState) -> dict[str, Any]:
    """
    Process human feedback and prepare for code regeneration.
    
    Args:
        state: Current agent state
        
    Returns:
        State updates for next iteration
    """
    return {
        "iteration": state["iteration"] + 1,
        "syntax_valid": False,  # Reset validation status
        "approved": False,  # Reset approval
    }


def should_continue_after_validation(state: StrategyAgentState) -> str:
    """
    Decide whether to continue to human review or regenerate code.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node name
    """
    if state["syntax_valid"]:
        return "human_review"
    elif state["iteration"] >= state["max_iterations"]:
        return "end"
    else:
        return "apply_feedback"


def should_continue_after_review(state: StrategyAgentState) -> str:
    """
    Decide whether to continue to backtest or apply feedback.
    
    Args:
        state: Current agent state
        
    Returns:
        Next node name
    """
    if state.get("approved", False):
        return "backtest"
    elif state["iteration"] >= state["max_iterations"]:
        return "end"
    else:
        return "apply_feedback"
