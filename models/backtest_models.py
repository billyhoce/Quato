from pydantic import BaseModel
from datetime import date
from typing import Dict, Any, Optional

US_FREE_STOCK_BUNDLE_MIN = "usstock-free-1min"
US_FREE_STOCK_BUNDLE_DAILY = "usstock-learn-1d"


class BacktestConfig(BaseModel):
    """
    Configuration for a backtest execution.

    Attributes:
        data_frequency: Only needs to set to request daily data from a minute bundle.
        capital_base: Initial capital for the backtest
        bundle: Data bundle code to use
        start_date: Start date of the backtest
        end_date: End date of the backtest
        progress: Level of progress reporting, default is "M" for monthly
        params: One or more strategy parameters (defined as module-level attributes in the algo file)
        filepath_or_buffer: Filepath or buffer to save backtest results
    """
    data_frequency: str = None
    capital_base: float = None
    bundle: str = None
    start_date: date = None
    end_date: date = None
    progress: str = "M"
    params: Dict[str, Any] = None
    filepath_or_buffer: Any

class BacktestResults(BaseModel):
    """Results from a backtest execution.
    
    Attributes:
        strategy_id: ID of the backtested strategy
        total_return: Total return percentage
        sharpe_ratio: Sharpe ratio of returns
        max_drawdown: Maximum drawdown percentage
        win_rate: Percentage of winning trades
        num_trades: Total number of trades
        execution_time: Time taken to run backtest
        metrics: Additional performance metrics
    """
    strategy_id: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    num_trades: int
    execution_time: float
    metrics: Dict[str, Any]