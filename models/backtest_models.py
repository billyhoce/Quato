from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any

US_FREE_STOCK_BUNDLE = "usstock-free-1min"

class BacktestConfig(BaseModel):
    """Configuration for a backtest.
    
    Attributes:
        strategy_id: ID of the strategy to backtest
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital for the backtest
        commission: Commission rate per trade
        slippage: Slippage model parameters
    """
    strategy_id: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    commission: float = 0.001
    slippage: Dict[str, Any] = None


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