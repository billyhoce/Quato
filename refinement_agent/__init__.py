"""Refinement Agent Module.

This module analyzes backtest results and automatically refines trading strategies
to improve performance. It uses LLMs to understand failure modes, propose
improvements, and iteratively optimize strategy parameters.

The module includes:
- Backtest result analysis
- Performance bottleneck identification
- Strategy parameter optimization
- Iterative refinement loops
"""

from .agent import RefinementAgent, RefinementType, RefinementSuggestion, RefinementResult

__all__ = ["RefinementAgent", "RefinementType", "RefinementSuggestion", "RefinementResult"]
__version__ = "0.1.0"
