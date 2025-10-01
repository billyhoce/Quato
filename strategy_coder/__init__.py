"""Strategy Coder Module.

This module translates trading hypotheses into executable QuantRocket strategy code.
It generates Python code that implements trading strategies with proper risk management,
position sizing, and order execution logic.

The module includes:
- Hypothesis to code translation
- Strategy code generation with templates
- Code validation and testing
- Integration with QuantRocket APIs
"""

from .coder import StrategyCoder, StrategyCode

__all__ = ["StrategyCoder", "StrategyCode"]
__version__ = "0.1.0"
