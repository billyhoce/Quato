"""Hypothesis Generation Module.

This module provides functionality for generating quantitative trading strategy
hypotheses using Large Language Models (LLMs). It analyzes market data, financial
indicators, and research papers to propose testable trading ideas.

The module includes:
- LLM-based hypothesis generation
- Market analysis and pattern recognition
- Research paper analysis
- Hypothesis scoring and ranking
"""

from .generator import HypothesisGenerator, Hypothesis

__all__ = ["HypothesisGenerator", "Hypothesis"]
__version__ = "0.1.0"
