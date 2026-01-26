"""
Strategy Agent Graph

LangGraph implementation with human-in-the-loop for strategy code generation.
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from strategy_agent.state import StrategyAgentState
from strategy_agent.config import AgentConfig
from strategy_agent.nodes import (
    parse_strategy_node,
    research_api_node,
    generate_code_node,
    validate_syntax_node,
    human_review_node,
    backtest_node,
    apply_feedback_node,
    should_continue_after_validation,
    should_continue_after_review,
)


def create_strategy_agent(config: AgentConfig):
    """
    Create the strategy agent graph with human-in-the-loop.
    
    The graph flow:
    1. Parse user input into hypothesis
    2. Research relevant API documentation
    3. Generate code using LLM
    4. Validate syntax
    5. If valid: Human review (HITL pause point)
    6. If approved: Run backtest
    7. If not approved or syntax invalid: Apply feedback and retry (up to max_iterations)
    
    Args:
        config: Agent configuration
        
    Returns:
        Compiled LangGraph application
    """
    # Define the graph
    workflow = StateGraph(StrategyAgentState)
    
    # Add nodes
    workflow.add_node("parse_strategy", parse_strategy_node)
    workflow.add_node("research_api", research_api_node)
    workflow.add_node("generate_code", generate_code_node)
    workflow.add_node("validate_syntax", validate_syntax_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("backtest", backtest_node)
    workflow.add_node("apply_feedback", apply_feedback_node)
    
    # Define the flow
    workflow.set_entry_point("parse_strategy")
    workflow.add_edge("parse_strategy", "research_api")
    workflow.add_edge("research_api", "generate_code")
    workflow.add_edge("generate_code", "validate_syntax")
    
    # Conditional edge after validation
    workflow.add_conditional_edges(
        "validate_syntax",
        should_continue_after_validation,
        {
            "human_review": "human_review",
            "apply_feedback": "apply_feedback",
            "end": END,
        }
    )
    
    # Conditional edge after human review
    workflow.add_conditional_edges(
        "human_review",
        should_continue_after_review,
        {
            "backtest": "backtest",
            "apply_feedback": "apply_feedback",
            "end": END,
        }
    )
    
    # After applying feedback, regenerate code
    workflow.add_edge("apply_feedback", "generate_code")
    
    # After backtest, end
    workflow.add_edge("backtest", END)
    
    # Use checkpoint saver for state persistence (required for HITL)
    memory = MemorySaver()
    
    # Compile the graph with interrupt before human review
    interrupt_nodes = []
    if config.enable_human_review:
        interrupt_nodes.append("human_review")
    
    app = workflow.compile(
        checkpointer=memory,
        interrupt_before=interrupt_nodes,
    )
    
    return app


def run_strategy_agent(
    user_input: str,
    config: AgentConfig,
    thread_id: str = "default"
) -> dict:
    """
    Run the strategy agent on user input.
    
    Args:
        user_input: Plaintext strategy description
        config: Agent configuration
        thread_id: Unique identifier for this conversation thread
        
    Returns:
        Final state dictionary
    """
    # Create the graph
    graph = create_strategy_agent(config)
    
    # Initial state
    initial_state: StrategyAgentState = {
        "user_input": user_input,
        "hypothesis": None,
        "generated_code": "",
        "api_context": "",
        "syntax_valid": False,
        "syntax_errors": None,
        "human_feedback": "",
        "approved": False,
        "backtest_results": None,
        "iteration": 0,
        "max_iterations": config.max_iterations,
        "messages": [],
    }
    
    # Run configuration with thread ID for checkpointing
    run_config = {"configurable": {"thread_id": thread_id}}
    
    # Execute the graph
    final_state = None
    for event in graph.stream(initial_state, run_config):
        print(f"Event: {event}")
        final_state = event
    
    return final_state


def resume_strategy_agent(
    config: AgentConfig,
    thread_id: str,
    approved: bool = False,
    feedback: str = ""
):
    """
    Resume the strategy agent after human review.
    
    Args:
        config: Agent configuration
        thread_id: Thread ID of the paused execution
        approved: Whether the human approved the code
        feedback: Human feedback for code revision
        
    Returns:
        Final state dictionary
    """
    # Create the graph
    graph = create_strategy_agent(config)
    
    # Run configuration
    run_config = {"configurable": {"thread_id": thread_id}}
    
    # Update state with human input
    graph.update_state(
        run_config,
        {
            "approved": approved,
            "human_feedback": feedback,
        }
    )
    
    # Resume execution
    final_state = None
    for event in graph.stream(None, run_config):
        print(f"Event: {event}")
        final_state = event
    
    return final_state
