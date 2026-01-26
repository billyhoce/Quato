"""
Agent Configuration

Pydantic configuration model for the strategy agent.
"""

from typing import Optional
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for the Strategy Agent."""
    
    model: str = Field(
        default="gpt-4o",
        description="LLM model to use for code generation"
    )
    
    api_key: Optional[str] = Field(
        default=None,
        description="API key for the LLM provider. If None, reads from environment."
    )
    
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM generation (lower = more deterministic)"
    )
    
    max_iterations: int = Field(
        default=5,
        ge=1,
        description="Maximum number of code generation iterations"
    )
    
    enable_human_review: bool = Field(
        default=True,
        description="Whether to pause for human review before backtesting"
    )
    
    syntax_validation: bool = Field(
        default=True,
        description="Whether to validate Python syntax before human review"
    )
