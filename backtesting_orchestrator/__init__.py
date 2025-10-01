"""Backtesting Orchestrator Module.

This module orchestrates the backtesting process for generated trading strategies
using QuantRocket. It manages data preparation, backtest execution, performance
analysis, and result visualization.

The module includes:
- Backtest configuration and execution
- Performance metrics calculation
- Result analysis and reporting
- Integration with QuantRocket backtesting engine
"""

from .orchestrator import BacktestingOrchestrator, BacktestConfig, BacktestResults

__all__ = ["BacktestingOrchestrator", "BacktestConfig", "BacktestResults"]
__version__ = "0.1.0"
